from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import and_, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models_db import TransactionScore
from api.schemas import FraudScoreResponse, PaginatedTransactions, TransactionIn, TransactionOut
from fraudradar.features import model_payload
from fraudradar.scoring import FraudScorer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["transactions"])
scorer = FraudScorer()


@router.get("", response_model=PaginatedTransactions)
async def list_transactions(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    risk_level: str | None = Query(None, regex="^(low|medium|high)$"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    is_fraud: bool | None = Query(None),
) -> PaginatedTransactions:
    """
    Get paginated list of transactions with optional filtering.
    
    Query parameters:
    - page: Page number (1-indexed)
    - limit: Items per page (1-500)
    - risk_level: Filter by risk level (low, medium, high)
    - date_from: Filter transactions after this date
    - date_to: Filter transactions before this date
    - is_fraud: Filter by fraud status (true/false)
    """
    # Build query
    statement = select(TransactionScore)
    
    # Apply filters
    filters = []
    if risk_level:
        filters.append(TransactionScore.risk_level == risk_level)
    if date_from:
        filters.append(TransactionScore.timestamp >= date_from)
    if date_to:
        filters.append(TransactionScore.timestamp <= date_to)
    if is_fraud is not None:
        filters.append(TransactionScore.is_fraud == is_fraud)
    
    if filters:
        statement = statement.where(and_(*filters))
    
    # Get total count
    count_statement = select(func.count()).select_from(TransactionScore)
    if filters:
        count_statement = count_statement.where(and_(*filters))
    total = await db.scalar(count_statement) or 0
    
    # Apply pagination and sorting
    statement = statement.order_by(desc(TransactionScore.created_at))
    statement = statement.limit(limit).offset((page - 1) * limit)
    
    # Execute
    result = await db.execute(statement)
    items = result.scalars().all()
    
    # Calculate pages
    pages = (total + limit - 1) // limit
    
    return PaginatedTransactions(
        items=[TransactionOut.from_orm(item) for item in items],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@router.get("/{transaction_id}", response_model=TransactionOut)
async def get_transaction(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
) -> TransactionOut:
    """Get a single transaction with full fraud score details."""
    statement = select(TransactionScore).where(TransactionScore.transaction_id == transaction_id)
    result = await db.execute(statement)
    transaction = result.scalar_one_or_none()
    
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    
    return TransactionOut.from_orm(transaction)


@router.post("/score", response_model=FraudScoreResponse, status_code=status.HTTP_201_CREATED)
async def score_transaction(
    payload: TransactionIn,
    db: AsyncSession = Depends(get_db),
) -> FraudScoreResponse:
    """
    Score a single transaction on-demand.
    
    This endpoint accepts a transaction and returns the fraud score immediately,
    without using Kafka. The result is also stored in the database.
    """
    raw_payload = payload.normalized_payload()
    enriched = model_payload(raw_payload)
    result = scorer.score(enriched)
    timestamp = payload.timestamp or datetime.now(tz=timezone.utc)
    
    record = TransactionScore(
        transaction_id=enriched["transaction_id"],
        timestamp=timestamp,
        amount=enriched["amount"],
        currency=enriched["currency"],
        merchant=enriched["merchant"],
        category=enriched["category"],
        card_id=enriched["card_id"],
        customer_id=enriched["customer_id"],
        country=enriched["country"],
        ip_address=enriched["ip_address"],
        device_id=enriched["device_id"],
        risk_score=result.risk_score,
        risk_level=result.risk_level,
        is_fraud=result.is_fraud,
        isolation_forest_score=result.isolation_forest_score,
        isolation_forest_anomaly=result.isolation_forest_anomaly,
        autoencoder_mse=result.autoencoder_mse,
        autoencoder_anomaly=result.autoencoder_anomaly,
        reasons=result.reasons,
        features=enriched["features"],
        raw_payload=raw_payload,
    )
    
    db.add(record)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transaction already scored") from exc
    
    await db.refresh(record)
    
    return FraudScoreResponse(
        transaction_id=record.transaction_id,
        risk_score=record.risk_score,
        risk_level=record.risk_level,
        is_fraud=record.is_fraud,
        isolation_forest_score=record.isolation_forest_score,
        isolation_forest_anomaly=record.isolation_forest_anomaly,
        autoencoder_mse=record.autoencoder_mse,
        autoencoder_anomaly=record.autoencoder_anomaly,
        reasons=record.reasons,
        scored_at=record.created_at,
    )


@router.websocket("/live")
async def websocket_live_transactions(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    WebSocket endpoint streaming latest transactions in real time.
    
    Reads from the database and polls every second for new transactions.
    Sends TransactionOut objects as JSON to the connected client.
    """
    await websocket.accept()
    logger.info("WebSocket client connected for live transactions")
    
    last_id = None
    try:
        while True:
            # Query new transactions since last check
            statement = select(TransactionScore).order_by(desc(TransactionScore.created_at))
            
            if last_id:
                statement = statement.where(TransactionScore.id > last_id)
            
            result = await db.execute(statement)
            transactions = result.scalars().all()
            
            # Send new transactions
            for transaction in transactions:
                if transaction.id > (last_id or ""):
                    last_id = transaction.id
                
                data = TransactionOut.from_orm(transaction)
                await websocket.send_text(data.model_dump_json())
            
            # Sleep before next poll
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=status.WS_1011_SERVER_ERROR)
        except Exception:
            pass
