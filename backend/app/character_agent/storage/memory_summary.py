"""面板完整摘要的派生索引；只更新本事件影响的记录，不缓存完整记忆模型。"""
import json


POOLS = (
    ("event", "event_memories", "summary"),
    ("observation", "observation_memories", "observation_summary"),
    ("knowledge", "knowledge_memories", "proposition"),
    ("social", "social_memories", "entity_id"),
    ("higher_order", "higher_order_memories", "meta_belief"),
)
EVENT_TYPES = frozenset({
    "character_perceived_event", "character_memory_correction", "character_agent_settlement_result",
    "character_agent_dialogue_response", "relational_belief_event", "knowledge_belief_event",
    "social_cognition_event", "higher_order_belief_event",
})
COLUMNS = {"actor_id", "pool", "entry_key", "first_index", "summary", "claim_record_json"}


def bundle_summary(bundle):
    return " | ".join(str(getattr(record, summary)) for _, field, summary in POOLS
                      for record in getattr(bundle, field) if getattr(record, summary))


def create_table(db):
    db.execute("CREATE TABLE character_session_memory_summary (actor_id TEXT NOT NULL, pool TEXT NOT NULL, entry_key TEXT NOT NULL, first_index INTEGER NOT NULL, summary TEXT NOT NULL, claim_record_json TEXT, PRIMARY KEY(actor_id,pool,entry_key))")
    db.execute("CREATE INDEX character_session_memory_summary_order ON character_session_memory_summary(actor_id,pool,first_index)")


def project(db, event):
    if event["event_type"] not in EVENT_TYPES:
        return
    # 复用原归一化、冲突及修正规则；唯一历史依赖为本命题的当前 claim。
    from app.character_agent.models.memory_consistency import MemoryFactClaim, memory_claim_key
    from app.character_agent.storage.memory_store import CharacterAgentMemoryStore

    actor_id = event["actor_id"]
    projection = CharacterAgentMemoryStore()
    claim = event["payload"].get("fact_claim")
    if event["event_type"] == "character_perceived_event" and isinstance(claim, dict):
        key = f"knowledge:{actor_id}:{memory_claim_key(MemoryFactClaim.model_validate(claim))}"
        row = db.execute("SELECT claim_record_json FROM character_session_memory_summary WHERE actor_id=? AND pool='knowledge' AND entry_key=?", (actor_id, key)).fetchone()
        if row is not None and row[0] is not None:
            projection._knowledge._entries_by_actor[actor_id] = [json.loads(row[0])]
    projection._ingest_event(event, include_working=False)
    bundle = projection.retrieval_record_bundle(actor_id)
    for pool, field, summary_field in POOLS:
        for record in getattr(bundle, field):
            # 高阶记忆按命题覆盖，保留首次出现顺序；其 memory_id 随来源变化。
            key = (json.dumps([record.subject_actor_id, record.proposition_key])
                   if pool == "higher_order" else record.memory_id)
            claim_record = record.model_dump_json() if pool == "knowledge" and record.claim is not None else None
            db.execute("INSERT INTO character_session_memory_summary VALUES (?,?,?,?,?,?) ON CONFLICT(actor_id,pool,entry_key) DO UPDATE SET summary=excluded.summary,claim_record_json=excluded.claim_record_json",
                       (actor_id, pool, key, event["event_index"], getattr(record, summary_field), claim_record))


def read(db, actor_id):
    # 文本本身仍按完整输出长度读取；省去事件解码、历史折叠和模型深拷贝。
    return " | ".join(row[0] for pool, _, _ in POOLS for row in db.execute(
        "SELECT summary FROM character_session_memory_summary WHERE actor_id=? AND pool=? ORDER BY first_index",
        (actor_id, pool)) if row[0])
