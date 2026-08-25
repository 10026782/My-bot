-- P23-M8B #2/#3 — explicit measured/unknown usage contract.
-- Additive and idempotent: existing rows/writers remain measured by default.

ALTER TABLE usage_events
    ADD COLUMN IF NOT EXISTS measurement_status TEXT NOT NULL DEFAULT 'measured';

ALTER TABLE usage_events
    ALTER COLUMN measurement_status SET DEFAULT 'measured',
    ALTER COLUMN measurement_status SET NOT NULL,
    ALTER COLUMN quantity_out DROP NOT NULL,
    ALTER COLUMN cost_usd DROP NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'usage_events'::regclass
          AND conname = 'usage_events_measurement_status_check'
    ) THEN
        ALTER TABLE usage_events
            ADD CONSTRAINT usage_events_measurement_status_check
            CHECK (measurement_status IN ('measured', 'unknown'));
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'usage_events'::regclass
          AND conname = 'usage_events_measurement_values_check'
    ) THEN
        ALTER TABLE usage_events
            ADD CONSTRAINT usage_events_measurement_values_check
            CHECK (
                (measurement_status = 'measured' AND quantity_out IS NOT NULL AND cost_usd IS NOT NULL)
                OR
                (measurement_status = 'unknown' AND quantity_out IS NULL AND cost_usd IS NULL)
            );
    END IF;
END $$;
