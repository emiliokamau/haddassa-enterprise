import uuid
from datetime import datetime, timedelta
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ..models import ClientProfile, Document, Filing, db
from ..services.audit import log_action
from ..services.authz import role_required

client_bp = Blueprint("client", __name__, url_prefix="/client")

_ALLOWED_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "csv", "jpg", "jpeg", "png"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in _ALLOWED_EXT


@client_bp.route("/dashboard")
@login_required
@role_required("client")
def dashboard():
    profile = ClientProfile.query.filter_by(user_id=current_user.id).first()
    filings = []
    pending_count = overdue_count = 0
    recent_filings = []

    if profile:
        filings = (
            Filing.query.filter_by(client_profile_id=profile.id)
            .order_by(Filing.due_date.asc())
            .all()
        )
        now = datetime.utcnow()
        in_progress_statuses = {"draft", "submitted", "under_review"}
        pending_count = sum(1 for f in filings if f.status in in_progress_statuses)
        overdue_count = sum(
            1
            for f in filings
            if f.due_date
            and f.due_date < now
            and f.status not in ("completed", "cancelled")
        )
        recent_filings = filings[:5]

    return render_template(
        "client_dashboard.html",
        profile=profile,
        filings=filings,
        pending_count=pending_count,
        overdue_count=overdue_count,
        recent_filings=recent_filings,
    )


@client_bp.route("/filings")
@login_required
@role_required("client")
def filings():
    profile = ClientProfile.query.filter_by(user_id=current_user.id).first()
    all_filings = []
    if profile:
        all_filings = (
            Filing.query.filter_by(client_profile_id=profile.id)
            .order_by(Filing.created_at.desc())
            .all()
        )
    return render_template("client_filings.html", filings=all_filings, profile=profile)


@client_bp.route("/filings/<int:filing_id>")
@login_required
@role_required("client")
def filing_detail(filing_id):
    profile = ClientProfile.query.filter_by(user_id=current_user.id).first()
    if profile is None:
        abort(404)
    filing = Filing.query.filter_by(id=filing_id, client_profile_id=profile.id).first_or_404()
    return render_template("client_filing_detail.html", filing=filing)


@client_bp.route("/filings/<int:filing_id>/upload", methods=["POST"])
@login_required
@role_required("client")
def upload_document(filing_id):
    profile = ClientProfile.query.filter_by(user_id=current_user.id).first_or_404()
    filing = Filing.query.filter_by(id=filing_id, client_profile_id=profile.id).first_or_404()

    if filing.status in ("completed", "cancelled"):
        flash("Documents cannot be uploaded to a completed or cancelled filing.", "error")
        return redirect(url_for("client.filing_detail", filing_id=filing_id))

    if "document" not in request.files or request.files["document"].filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("client.filing_detail", filing_id=filing_id))

    file = request.files["document"]
    if not _allowed_file(file.filename):
        flash(
            "File type not allowed. Upload PDF, Word, Excel, CSV, or image files.", "error"
        )
        return redirect(url_for("client.filing_detail", filing_id=filing_id))

    original_name = secure_filename(file.filename)
    ext = original_name.rsplit(".", 1)[-1].lower()
    stored_name = f"{uuid.uuid4().hex}.{ext}"

    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    file.save(str(upload_dir / stored_name))

    doc = Document(
        filing_id=filing.id,
        original_filename=original_name,
        storage_path=stored_name,
    )
    db.session.add(doc)
    log_action(
        "document_upload",
        entity_type="document",
        entity_id=filing.id,
        details={"filename": original_name},
    )
    db.session.commit()
    flash("Document uploaded successfully.", "success")
    return redirect(url_for("client.filing_detail", filing_id=filing_id))


@client_bp.route("/documents/<int:doc_id>/download")
@login_required
@role_required("client")
def download_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if doc is None:
        abort(404)
    profile = ClientProfile.query.filter_by(user_id=current_user.id).first_or_404()
    if doc.filing.client_profile_id != profile.id:
        abort(403)
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    return send_from_directory(
        str(upload_dir),
        doc.storage_path,
        as_attachment=True,
        download_name=doc.original_filename,
    )

