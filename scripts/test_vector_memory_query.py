#!/usr/bin/env python3
"""
Test script to verify vector memory queries work correctly.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from finance_feedback_engine.memory.vector_store import VectorMemory

def main():
    print("\n" + "="*80)
    print("TESTING FFE VECTOR MEMORY QUERIES")
    print("="*80 + "\n")
    
    # Load vector memory
    vector_memory = VectorMemory(storage_path="data/memory/vectors.json")
    
    print(f"✅ Vector memory loaded successfully")
    print(f"   Total vectors: {len(vector_memory.vectors)}")
    print(f"   Total records: {len(vector_memory.ids)}\n")
    
    # Test queries
    test_queries = [
        "What should I do in a bull market?",
        "How to trade during a bear market crash?",
        "Mixed market bidirectional trading strategies",
        "Short position exit strategies",
        "Best winning trades in volatile conditions"
    ]
    
    for query in test_queries:
        print(f"\n{'─'*80}")
        print(f"Query: [bold]{query}[/bold]\n")
        
        results = vector_memory.find_similar(query, top_k=3)
        
        if results:
            print(f"Found {len(results)} relevant lessons:\n")
            for i, (record_id, similarity, metadata) in enumerate(results, 1):
                print(f"{i}. [ID: {record_id}] (Similarity: {similarity:.3f})")
                
                # Handle nested metadata structure
                meta = metadata.get('metadata', metadata)
                
                print(f"   Insight: {meta.get('key_insight', 'N/A')}")
                if 'market_conditions' in meta:
                    market_type = meta['market_conditions'].get('market_type', 'unknown')
                    print(f"   Market: {market_type.upper()}")
                if 'outcome' in meta:
                    outcome = meta['outcome']
                    if 'pnl' in outcome:
                        print(f"   P&L: ${outcome['pnl']:.2f}")
                    elif 'total_pnl' in outcome:
                        print(f"   Total P&L: ${outcome['total_pnl']:.2f}")
                        print(f"   Win Rate: {outcome.get('win_rate', 0):.1f}%")
                print()
        else:
            print("⚠️  No results found")
    
    print("\n" + "="*80)
    print("VECTOR MEMORY QUERY TEST COMPLETE")
    print("="*80 + "\n")

if __name__ == '__main__':
    main()
