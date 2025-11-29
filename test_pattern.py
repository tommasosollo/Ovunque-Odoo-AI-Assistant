import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

query = "mostrami i clienti con più di 10 fatture"
query_lower = query.lower()

pattern = r'(clienti|partner|cliente|customer|fornitore|supplier).*?(?:con|that have|with).*?(\d+)\s*(?:fatture|invoice|document)'

print(f"Testing query: '{query}'")
print(f"Lowercase: '{query_lower}'")
print(f"Pattern: {pattern}\n")

match = re.search(pattern, query_lower, re.IGNORECASE)
if match:
    print("MATCH: YES")
    print(f"  Full match: '{match.group(0)}'")
    print(f"  Group 1 (entity): '{match.group(1)}'")
    print(f"  Group 2 (number): '{match.group(2)}'")
else:
    print("MATCH: NO")

# Test count extraction
count_match = re.search(r'(\d+)', query_lower)
if count_match:
    print(f"\nCOUNT EXTRACTED: {count_match.group(1)}")
else:
    print("\nCOUNT NOT FOUND")
