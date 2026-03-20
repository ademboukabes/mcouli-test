import sys
import os


def clean_schema(file_path: str) -> None:
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    # Detect encoding by checking the first few bytes
    encoding = "utf-8"
    with open(file_path, "rb") as f:
        raw = f.read(4)
        if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
            encoding = "utf-16"
            print("Detected UTF-16 encoding from pg_dump. Converting...")

    try:
        with open(file_path, "r", encoding=encoding) as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="latin-1") as f:
            lines = f.readlines()

    clean_lines = []
    for line in lines:
        if "pg_catalog.set_config" in line:
            continue
        if line.strip().startswith("\\"):
            continue
        if "CREATE EXTENSION" in line:
            continue
        clean_lines.append(line)

    with open(file_path, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(clean_lines)

    print(f"Successfully cleaned and converted {file_path} to UTF-8 for sqlc.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "db/schema.sql"
    clean_schema(target)
