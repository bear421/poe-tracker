import duckdb

conn = duckdb.connect(f"user_data/poe_tracker.duckdb")
conn.execute("""CREATE TABLE IF NOT EXISTS maps (id string, data JSON)""")
conn.execute("""CREATE TABLE IF NOT EXISTS instance_manager_state (id string, field string, data JSON)""")
conn.execute("""CREATE TABLE IF NOT EXISTS xp_snapshots (id string, data JSON)""")
conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_instance_manager_state_field ON instance_manager_state (field)""")
conn.execute("""CREATE TABLE IF NOT EXISTS gui_state (field string, data JSON)""")
conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_gui_state_field ON instance_manager_state (field)""")
conn.execute("""CREATE TABLE IF NOT EXISTS encounters (id string, data JSON)""")
