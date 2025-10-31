from __future__ import annotations

import logging
from datetime import datetime
import uuid
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - optional dependency
    from google.api_core import exceptions as gcloud_exceptions  # type: ignore
except ImportError:  # pragma: no cover - local fallback
    class _NotFound(Exception):
        ...

    class gcloud_exceptions:  # type: ignore
        NotFound = _NotFound

try:  # pragma: no cover - optional dependency
    from google.cloud import firestore  # type: ignore
except ImportError:  # pragma: no cover - local fallback
    firestore = None

from ..core.config import get_settings
from ..models import (
    Cast,
    ChatEvent,
    ChatEventCreate,
    Job,
    JobCreate,
    JobStatus,
    PersonaTemplate,
    PersonaTemplateCreate,
    PersonaTemplateUpdate,
    PromptVersion,
    PromptVersionCreate,
    ReservationEvent,
    ReservationEventCreate,
    Store,
)

logger = logging.getLogger(__name__)


class FirestoreRepository:
    """Firestore backed persistence with in-memory fallback for local dev."""

    def __init__(self) -> None:
        settings = get_settings()
        self._namespace = settings.firestore_namespace
        self._client = firestore.Client(project=settings.project_id) if firestore else None
        self._jobs: Dict[str, Job] = {}
        self._prompts: Dict[str, Dict[str, PromptVersion]] = {}
        self._persona_templates: Dict[str, Dict[str, Any]] = {
            "b2b-saas-akari": {
                "id": "b2b-saas-akari",
                "label": "B2B SaaS リード獲得（井上あかり）",
                "reader": {
                    "job_role": "B2Bマーケティングマネージャー",
                    "experience_years": "3-5年",
                    "needs": [
                        "ナーチャリングの歩留まりを改善したい",
                        "一次情報を使って決裁者を動かしたい",
                        "営業/CSと連携できるコンテンツ設計を知りたい",
                    ],
                    "prohibited_expressions": ["初心者向け", "無料ですぐにできる"],
                },
                "writer": {
                    "name": "井上あかり",
                    "role": "B2B SaaSのシニアコンテンツストラテジスト",
                    "expertise": "B2Bマーケティングの戦略立案とデータドリブンなSEO改善施策に精通",
                    "voice": "共感とロジックを両立させる実務家視点",
                    "mission": "読者の迷いを解き、行動の背中を押すコンテンツを届ける",
                    "qualities": [
                        "抽象と具体を往復しながらストーリーで魅せる",
                        "数字と一次情報をもとに説得力を担保する",
                        "視覚・聴覚・体感のVAKで読者の想像を喚起する",
                    ],
                },
                "extras": {
                    "intended_cta": "資料請求",
                    "notation_guidelines": "英数字は半角。一次情報は [Source: URL] で表記。",
                    "quality_rubric": "standard",
                    "preferred_sources": [
                        "https://www.meti.go.jp/",
                        "https://www.stat.go.jp/",
                        "https://thinkwithgoogle.com/",
                        "https://www.gartner.com/en",
                        "https://hbr.org/",
                    ],
                    "reference_media": [
                        "HubSpotブログ",
                        "Think with Google",
                        "日経クロストレンド",
                        "海外調査レポート（Gartner, McKinsey等）",
                    ],
                    "supporting_keywords": [
                        "マーケティングオートメーション",
                        "インサイドセールス 体制",
                        "リードマネジメント プロセス",
                    ],
                    "reference_urls": ["https://knowledge.seo-drafter.com/digital-marketing"],
                },
                "heading": {
                    "mode": "auto",
                    "overrides": [],
                },
            },
            "smb-media-editor": {
                "id": "smb-media-editor",
                "label": "中小企業向けオウンドメディア編集",
                "reader": {
                    "job_role": "中小企業の広報・マーケ担当",
                    "experience_years": "1-3年",
                    "needs": [
                        "限られた予算でも成果が出る事例を知りたい",
                        "社内の専門家を巻き込む方法を学びたい",
                        "中長期で評価されるコンテンツの型を知りたい",
                    ],
                    "prohibited_expressions": ["専門家に任せましょう", "すぐに結果が出ます"],
                },
                "writer": {
                    "name": "田中みさき",
                    "role": "中堅企業のコンテンツマーケティング編集長",
                    "expertise": "SMB領域の顧客理解、ヒアリング設計、社内ナレッジ編集",
                    "voice": "親しみやすさとデータを両立する伴走型の語り口",
                    "mission": "読者の「うちでもできそう」を後押しする再現性の高い手順を届ける",
                    "qualities": [
                        "読者の疑問を先回りしてQA形式で補足する",
                        "ケーススタディはBefore/Afterで描写する",
                        "一次情報と現場の声をセットで引用する",
                    ],
                },
                "extras": {
                    "intended_cta": "相談フォーム",
                    "notation_guidelines": "英数字は半角、固有名詞は正式名称で統一。",
                    "quality_rubric": "eeat-focused",
                    "preferred_sources": ["https://prtimes.jp/", "https://www.soumu.go.jp/"],
                    "reference_media": ["MarkeZine", "ferret", "note公式ブログ"],
                    "supporting_keywords": ["オウンドメディア 成功事例", "社内ナレッジ 取材"],
                    "reference_urls": ["https://knowledge.seo-drafter.com/content-strategy-smb"],
                },
                "heading": {
                    "mode": "manual",
                    "overrides": [
                        "イントロダクション",
                        "社内ナレッジの掘り起こし方",
                        "運用体制と成果測定",
                    ],
                },
            },
        }
        self._stores: Dict[str, Store] = {}
        self._casts: Dict[str, Cast] = {}
        self._chat_events: Dict[str, ChatEvent] = {}
        self._reservation_events: Dict[str, ReservationEvent] = {}

    def _doc_path(self, collection: str, doc_id: str) -> str:
        if self._namespace:
            return f"{self._namespace}/{collection}/{doc_id}"
        return f"{collection}/{doc_id}"

    def _collection(self, name: str):
        if not self._client:
            return None
        if self._namespace:
            return self._client.collection(f"{self._namespace}/{name}")
        return self._client.collection(name)

    # Jobs
    def create_job(self, job_id: str, payload: JobCreate, draft_id: Optional[str] = None) -> Job:
        now = datetime.utcnow()
        job = Job(
            id=job_id,
            status=JobStatus.pending,
            created_at=now,
            updated_at=now,
            payload=payload,
            draft_id=draft_id,
        )
        if self._client:
            doc_ref = self._client.document(self._doc_path("jobs", job_id))
            doc_ref.set(job.model_dump())
        else:
            self._jobs[job_id] = job
        return job

    def update_job(self, job_id: str, **updates: Any) -> Optional[Job]:
        current = self.get_job(job_id)
        if not current:
            return None
        data = current.model_dump()
        data.update(updates)
        data["updated_at"] = datetime.utcnow()
        job = Job(**data)
        if self._client:
            doc_ref = self._client.document(self._doc_path("jobs", job_id))
            doc_ref.set(job.model_dump())
        else:
            self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        if self._client:
            doc_ref = self._client.document(self._doc_path("jobs", job_id))
            try:
                snapshot = doc_ref.get()
            except gcloud_exceptions.NotFound:  # pragma: no cover
                return None
            if not snapshot.exists:
                return None
            return Job(**snapshot.to_dict())
        return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 50, order_by: str = "created_at") -> List[Job]:
        """List jobs ordered by creation time (newest first)."""
        jobs = []
        if self._client:
            collection = self._client.collection("jobs" if not self._namespace else f"{self._namespace}/jobs")
            query = collection.order_by(order_by, direction=firestore.Query.DESCENDING).limit(limit)
            try:
                for doc in query.stream():
                    jobs.append(Job(**doc.to_dict()))
            except Exception as e:
                logger.error("Error listing jobs: %s", e)
        else:
            # In-memory fallback
            jobs = sorted(
                self._jobs.values(),
                key=lambda j: j.created_at if j.created_at else datetime.min,
                reverse=True
            )[:limit]
        return jobs

    # Prompt versions
    def create_prompt_version(self, data: PromptVersionCreate) -> PromptVersion:
        entry = PromptVersion(
            version=data.version,
            templates=data.templates,
            variables=data.variables,
            description=data.description,
        )
        prompt_versions = self._prompts.setdefault(data.prompt_id, {})
        prompt_versions[data.version] = entry

        if self._client:
            doc_ref = self._client.document(self._doc_path("prompts", data.prompt_id))
            doc_ref.set({"versions": {data.version: entry.model_dump()}}, merge=True)
        return entry

    def get_prompt_version(self, prompt_id: str, version: Optional[str]) -> Optional[PromptVersion]:
        if self._client:
            doc_ref = self._client.document(self._doc_path("prompts", prompt_id))
            snapshot = doc_ref.get()
            if snapshot.exists:
                data = snapshot.to_dict()
                versions: Dict[str, Dict[str, Any]] = data.get("versions", {})
                if not version and versions:
                    version = sorted(versions.keys())[-1]
                if version and version in versions:
                    return PromptVersion(**versions[version])
            return None

        prompt_versions = self._prompts.get(prompt_id, {})
        if not version and prompt_versions:
            version = sorted(prompt_versions.keys())[-1]
        return prompt_versions.get(version) if version else None

    # Persona templates
    def list_persona_templates(self) -> List[PersonaTemplate]:
        templates: List[PersonaTemplate] = []
        if self._client:
            collection = self._collection("persona_templates")
            try:
                for doc in collection.stream():
                    data = doc.to_dict() or {}
                    data["id"] = doc.id
                    templates.append(PersonaTemplate(**data))
            except Exception as exc:
                logger.error("Error fetching persona templates: %s", exc)

        if not templates:
            templates = [PersonaTemplate(**data) for data in self._persona_templates.values()]
        return templates

    def get_persona_template(self, template_id: str) -> Optional[PersonaTemplate]:
        if self._client:
            doc_ref = self._client.document(self._doc_path("persona_templates", template_id))
            try:
                snapshot = doc_ref.get()
            except gcloud_exceptions.NotFound:  # pragma: no cover
                snapshot = None
            if snapshot and snapshot.exists:
                data = snapshot.to_dict() or {}
                data["id"] = template_id
                return PersonaTemplate(**data)
        data = self._persona_templates.get(template_id)
        return PersonaTemplate(**data) if data else None

    def create_persona_template(self, payload: PersonaTemplateCreate) -> PersonaTemplate:
        if self.get_persona_template(payload.id):
            raise ValueError("template_exists")
        template = PersonaTemplate(**payload.model_dump())
        if self._client:
            doc_ref = self._client.document(self._doc_path("persona_templates", template.id))
            doc_ref.set(template.model_dump(exclude={"id"}))
        self._persona_templates[template.id] = template.model_dump()
        return template

    def update_persona_template(self, template_id: str, payload: PersonaTemplateUpdate) -> Optional[PersonaTemplate]:
        existing = self.get_persona_template(template_id)
        if not existing:
            return None
        update_data = payload.model_dump(exclude_unset=True)
        current = existing.model_dump()
        for key, value in update_data.items():
            current[key] = value
        template = PersonaTemplate(**current)
        if self._client:
            doc_ref = self._client.document(self._doc_path("persona_templates", template_id))
            doc_ref.set(template.model_dump(exclude={"id"}), merge=True)
        self._persona_templates[template_id] = template.model_dump()
        return template

    def delete_persona_template(self, template_id: str) -> bool:
        removed = False
        if self._client:
            doc_ref = self._client.document(self._doc_path("persona_templates", template_id))
            try:
                doc_ref.delete()
                removed = True
            except gcloud_exceptions.NotFound:  # pragma: no cover
                removed = False
        if template_id in self._persona_templates:
            self._persona_templates.pop(template_id)
            removed = True
        return removed

    # Stores and casts
    def upsert_store(self, store: Store) -> Store:
        data = store.model_dump(exclude_none=True)
        if self._client:
            doc_ref = self._client.document(self._doc_path("stores", store.id))
            doc_ref.set(data, merge=True)
        self._stores[store.id] = store
        return store

    def get_store(self, store_id: str) -> Optional[Store]:
        if self._client:
            doc_ref = self._client.document(self._doc_path("stores", store_id))
            try:
                snapshot = doc_ref.get()
            except gcloud_exceptions.NotFound:  # pragma: no cover
                snapshot = None
            if snapshot and snapshot.exists:
                data = snapshot.to_dict() or {}
                data["id"] = store_id
                return Store(**data)
        return self._stores.get(store_id)

    def upsert_cast(self, cast: Cast) -> Cast:
        data = cast.model_dump(exclude_none=True)
        if self._client:
            doc_ref = self._client.document(self._doc_path("casts", cast.id))
            doc_ref.set(data, merge=True)
        self._casts[cast.id] = cast
        return cast

    def get_cast(self, cast_id: str) -> Optional[Cast]:
        if self._client:
            doc_ref = self._client.document(self._doc_path("casts", cast_id))
            try:
                snapshot = doc_ref.get()
            except gcloud_exceptions.NotFound:  # pragma: no cover
                snapshot = None
            if snapshot and snapshot.exists:
                data = snapshot.to_dict() or {}
                data["id"] = cast_id
                return Cast(**data)
        return self._casts.get(cast_id)

    # Events
    def create_chat_event(self, payload: ChatEventCreate) -> ChatEvent:
        event_id = payload.event_id or str(uuid.uuid4())
        event = ChatEvent(
            id=event_id,
            cast_id=payload.cast_id,
            store_id=payload.store_id,
            sender_name=payload.sender_name,
            customer_name=payload.customer_name,
            message=payload.message,
            channel=payload.channel,
            unread_count=payload.unread_count,
            metadata=dict(payload.metadata),
            sent_at=payload.sent_at,
        )
        if self._client:
            collection = self._collection("chat_events")
            if collection:
                collection.document(event.id).set(event.model_dump())
        self._chat_events[event.id] = event
        return event

    def list_chat_events(self, cast_id: Optional[str] = None, limit: int = 20) -> List[ChatEvent]:
        events: List[ChatEvent] = []
        if self._client:
            collection = self._collection("chat_events")
            if collection:
                query = collection.order_by(
                    "recorded_at", direction=firestore.Query.DESCENDING
                ).limit(limit)
                if cast_id:
                    query = query.where("cast_id", "==", cast_id)
                try:
                    for doc in query.stream():
                        data = doc.to_dict() or {}
                        data["id"] = doc.id
                        events.append(ChatEvent(**data))
                except Exception as exc:
                    logger.error("Error listing chat events: %s", exc)
        if not events:
            events = [event for event in self._chat_events.values() if not cast_id or event.cast_id == cast_id]
            events.sort(key=lambda entry: entry.recorded_at, reverse=True)
        return events[:limit]

    def create_reservation_event(self, payload: ReservationEventCreate) -> ReservationEvent:
        event_id = payload.event_id or str(uuid.uuid4())
        event = ReservationEvent(
            id=event_id,
            reservation_id=payload.reservation_id,
            cast_id=payload.cast_id,
            store_id=payload.store_id,
            customer_name=payload.customer_name,
            customer_contact=payload.customer_contact,
            menu_name=payload.menu_name,
            channel=payload.channel,
            note=payload.note,
            metadata=dict(payload.metadata),
            start_at=payload.start_at,
            end_at=payload.end_at,
            status=payload.status,
            created_at=payload.created_at,
        )
        if self._client:
            collection = self._collection("reservation_events")
            if collection:
                collection.document(event.id).set(event.model_dump())
        self._reservation_events[event.id] = event
        return event

    def list_reservation_events(self, cast_id: Optional[str] = None, limit: int = 20) -> List[ReservationEvent]:
        events: List[ReservationEvent] = []
        if self._client:
            collection = self._collection("reservation_events")
            if collection:
                query = collection.order_by(
                    "start_at", direction=firestore.Query.DESCENDING
                ).limit(limit)
                if cast_id:
                    query = query.where("cast_id", "==", cast_id)
                try:
                    for doc in query.stream():
                        data = doc.to_dict() or {}
                        data["id"] = doc.id
                        events.append(ReservationEvent(**data))
                except Exception as exc:
                    logger.error("Error listing reservation events: %s", exc)
        if not events:
            events = [
                event for event in self._reservation_events.values() if not cast_id or event.cast_id == cast_id
            ]
            events.sort(key=lambda entry: entry.start_at, reverse=True)
        return events[:limit]
