"""Run every sql/*.sql file against the DuckDB database, in order, and export every r_* result table to CSV.
Usage: python3 03_run_sql.py <db_path> <sql_dir> <results_dir>"""
import sys, os, glob, time, duckdb
db, sql_dir, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
con = duckdb.connect(db); con.execute("SET memory_limit='3GB'")
for f in sorted(glob.glob(os.path.join(sql_dir, "*.sql"))):
    t = time.time(); con.execute(open(f).read()); print(f"ran {os.path.basename(f)} in {time.time()-t:.1f}s")
for (t,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'r\\_%' ESCAPE '\\' ORDER BY 1").fetchall():
    con.execute(f"COPY {t} TO '{out}/{t}.csv' (HEADER)")
    print("exported", t, con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0], "rows")
