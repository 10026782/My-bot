# Writer / Authority Registration Registry

This registry is the explicit architecture decision boundary for new
writer/store/repository/authority implementations. It is intentionally exact:
one path and symbol per row, with a named owner and a decision/reference ID.
Adding a row does not grant runtime authority by itself; it records the review
that approved the implementation and its single owner.

| Path | Symbol | Owner | Architecture decision |
| --- | --- | --- | --- |
| `test_f52_g4_s1_lead_memory_writer.py` | `<module>` | `action_contracts` | `F52-G4-S1` |
| `test_f52_g4_s4_interaction_task_writer.py` | `<module>` | `action_contracts` | `F52-G4-S4` |
| `test_f52_g4_s5_weekly_quest_reset.py` | `<module>` | `action_contracts` | `F52-G4-S5` |
| `commercial_completion.py` | `CommercialCompletionWriter` | commercial_crm | `decision.commercial_completion_foundation` |
| `commercial_completion_routing.py` | `CommercialCompletionRouter` | commercial_crm | `decision.commercial_completion_routing` |
| `commercial_crm.py` | `find_or_create_organization` | commercial_crm | `decision.commercial_v2_mutation_primitives` |
| `commercial_crm.py` | `create_charge` | commercial_crm | `decision.commercial_v2_mutation_primitives` |
| `commercial_crm.py` | `create_charge_payment` | commercial_crm | `decision.commercial_v2_mutation_primitives` |
| `recruitment_crm.py` | `execute_recruitment_write` | recruitment | `decision.recruitment_worker_data_model_phase2` |
| `test_recruitment_writers.py` | `<module>` | recruitment | `decision.recruitment_worker_data_model_phase2` |
| `test_phase0_commercial_crm_update_authority.py` | `<module>` | commercial_crm | `decision.phase0_commercial_crm_update_authority` |
| `session_store.py` | `save_business_draft` | business_draft | `decision.businessdraft_phase2_sessions_persistence` |
| `core/task_writer.py` | `<module>` | tasks | `decision.task_golden_writer` |
| `core/task_writer.py` | `TaskWriteRejected` | tasks | `decision.task_golden_writer` |
| `test_task_golden_writer.py` | `<module>` | tasks | `decision.task_golden_writer` |
