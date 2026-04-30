import sys
import os
sys.path.insert(0, 'src/ingestion')

# Import and run the main ingestion script
from ingestion import main

if __name__ == "__main__":
    main()