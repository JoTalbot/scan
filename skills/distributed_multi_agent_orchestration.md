# 🧠 Agent Skill: Distributed Multi-Agent Orchestration & Pre-Step Research

> **Skill Slug:** `distributed_multi_agent_orchestration`  
> **Status:** Standard Operating Procedure  
> **Author:** Agent-Primary  

---

## 🎯 Назначение
Протокол координации группы независимых ИИ-агентов на разных машинах, исключающий коллизии, гарантирующий актуальность статуса и требующий предварительного исследования интернета и существующих скилов перед каждым действием.

---

## 📋 Обязательный цикл агента перед каждым шагом

```
1. Git Pull & State Check (STATUS.md / agent_state.json)
       │
       ▼
2. Deep Research (Internet, GitHub, RFCs, skills/)
       │
       ▼
3. Task Lock & Step Announce (agent_sync.py lock/step)
       │
       ▼
4. Implementation & Validation
       │
       ▼
5. Convert Operation Log into Reusable Skill (skills/<name>.md)
       │
       ▼
6. Git Commit, Status Update & Push
```

---

## 🔍 Инструкция по предварительному исследованию (Pre-Step Research)
Перед написанием любого алгоритма агент выполняет:
1. Поиск существующих RFC и стандартов (например, RFC 4632 для CIDR, RFC 4291 для IPv6).
2. Поиск проверенных открытых библиотек и реализаций.
3. Проверку локальных файлов в директории `skills/`.
4. Сравнение производительности и выбор оптимального пути.
