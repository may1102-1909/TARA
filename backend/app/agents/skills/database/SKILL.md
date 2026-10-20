---
name: database
description: Standards for reliable data modeling, safe SQL queries, in-memory caching, and persistence mechanisms.
---

# Database & Persistence Engineering Skill

Use this skill when implementing data storage, persistence, repositories, or caching layers.

## 1. Storage & Schema Design
- For lightweight or embedded needs, prefer SQLite (`sqlite3`) or standard in-memory dictionaries with threading locks.
- Clearly define table schemas with primary keys, foreign keys, timestamps, and indexes on frequently queried fields.
- Use explicit types (TEXT, INTEGER, REAL, BLOB, TIMESTAMP).

## 2. Injection Prevention & Parameterization
- NEVER concatenate user input directly into SQL strings (`f"SELECT * FROM users WHERE name='{user_input}'"` is strictly forbidden).
- ALWAYS use parameterized queries with placeholders (`cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))`).
- Validate data types and lengths using Pydantic models before passing to the storage layer.

## 3. Repository Pattern & Clean Abstraction
- Encapsulate data access logic in dedicated Repository or Storage classes (`class ItemRepository: ...`).
- Provide standard CRUD operations:
  - `create(item: ItemCreate) -> Item`
  - `get_by_id(item_id: str) -> Optional[Item]`
  - `list_all(limit: int = 100, offset: int = 0) -> List[Item]`
  - `update(item_id: str, patch: ItemUpdate) -> Optional[Item]`
  - `delete(item_id: str) -> bool`
- Ensure database connections and cursor transactions are managed cleanly with context managers (`with sqlite3.connect(...) as conn:`).
