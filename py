import mysql.connector

# ====== DB CONFIG ======
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "biznes2025",
    "database": "telegram_bot"
}

# ====== CONNECT ======
conn = mysql.connector.connect(**db_config)
cursor = conn.cursor()

# ====== GET TABLES ======
cursor.execute("SHOW TABLES")
tables = cursor.fetchall()

# ====== WRITE SCHEMA ======
with open("schema.sql", "w", encoding="utf-8") as f:  # "w" => overwrite qiladi
    f.write(f"-- Schema dump for database: telegram_bot\n\n")

    for (table_name,) in tables:
        cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
        result = cursor.fetchone()

        create_statement = result[1]

        f.write(f"-- ----------------------------\n")
        f.write(f"-- Table: {table_name}\n")
        f.write(f"-- ----------------------------\n")
        f.write(f"{create_statement};\n\n")

# ====== CLEANUP ======
cursor.close()
conn.close()

print("schema.sql muvaffaqiyatli yaratildi (overwrite qilingan bo‘lishi mumkin).")