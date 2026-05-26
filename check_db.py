import sqlite3
conn = sqlite3.connect('data/applicants.db')
c = conn.cursor()
print('Total:', c.execute("SELECT COUNT(*) FROM applicants").fetchone()[0])
print('Pending:', c.execute("SELECT COUNT(*) FROM applicants WHERE status='pending'").fetchone()[0])
print('Accepted:', c.execute("SELECT COUNT(*) FROM applicants WHERE status='accepted'").fetchone()[0])
print('Rejected:', c.execute("SELECT COUNT(*) FROM applicants WHERE status='rejected'").fetchone()[0])
for row in c.execute("SELECT full_name, status FROM applicants ORDER BY status, full_name"):
    print(f"  {row[1]:10s} | {row[0]}")
conn.close()
