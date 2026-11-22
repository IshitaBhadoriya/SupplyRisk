
from datetime import datetime

from app.database import SessionLocal
from app.models import IngestionStatus


def _get_or_create_status(db, package_id, source):
    record = (
        db.query(IngestionStatus)
        .filter_by(
            package_id=package_id,
            source=source
        )
        .first()
    )

    if record is None:
        record = IngestionStatus(
            package_id=package_id,
            source=source,
            status="pending",
            records_found=0
        )
        db.add(record)
        db.flush()

    return record


def mark_running(package_id, source):
    db = SessionLocal()

    try:
        record = _get_or_create_status(
            db, package_id, source
        )

        record.status = "running"
        record.last_attempt_at = datetime.utcnow()
        record.error_message = None

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def mark_success(package_id, source, records_found):
    db = SessionLocal()

    try:
        now = datetime.utcnow()

        record = _get_or_create_status(
            db, package_id, source
        )

        record.status = "success"
        record.last_attempt_at = now
        record.last_success_at = now
        record.records_found = records_found
        record.error_message = None

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def mark_failed(package_id, source, error):
    db = SessionLocal()

    try:
        record = _get_or_create_status(
            db, package_id, source
        )

        record.status = "failed"
        record.last_attempt_at = datetime.utcnow()
        record.error_message = str(error)[:4000]

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def mark_not_found(package_id, source, error):
    """Mark a permanently missing package so it is not retried."""

    db = SessionLocal()

    try:
        record = _get_or_create_status(
            db, package_id, source
        )

        record.status = "not_found"
        record.last_attempt_at = datetime.utcnow()
        record.error_message = str(error)[:4000]

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
