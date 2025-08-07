#!/usr/bin/env python3
"""
Pythonic ArXiv Paper Downloader with Praval's Decorator API

Demonstrates elegant multi-agent coordination for downloading the top 5 
technical papers on any topic from arXiv.

Before (verbose): 460+ lines with complex state management
After (pythonic): ~150 lines with simple decorated functions

Usage:
    python arxiv_paper_downloader.py
"""

import sys
import re
import json
import logging
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, '/Users/rajesh/Github/praval/src')

from praval import agent, chat, broadcast, start_agents

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Simple shared state - just Python data structures!
papers = {"found": [], "ranked": [], "downloaded": [], "query": "", "target": 5}

# ==========================================
# CONCURRENT AGENTS AS DECORATED FUNCTIONS
# ==========================================

@agent("searcher", channel="papers", responds_to=["search_request"])
def search_arxiv_papers(spore):
    """Find papers on arXiv and add to found list."""
    query = spore.knowledge.get("query", "")
    if not query: return
    
    logging.info(f"🔍 Searching arXiv for: '{query}'")
    
    # Query arXiv API 
    url = f"http://export.arxiv.org/api/query?search_query=all:{quote_plus(query)}&max_results=15&sortBy=relevance"
    response = requests.get(url, timeout=10)
    root = ET.fromstring(response.content)
    
    found_papers = []
    for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
        try:
            title = entry.find('{http://www.w3.org/2005/Atom}title').text.strip()
            summary = entry.find('{http://www.w3.org/2005/Atom}summary').text.strip()
            arxiv_id = entry.find('{http://www.w3.org/2005/Atom}id').text.split('/')[-1]
            authors = [a.find('{http://www.w3.org/2005/Atom}name').text 
                      for a in entry.findall('{http://www.w3.org/2005/Atom}author')]
            
            found_papers.append({
                "id": arxiv_id, "title": title, "summary": summary, 
                "authors": authors, "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            })
        except: continue
    
    papers["found"] = found_papers
    papers["query"] = query
    logging.info(f"✅ Found {len(found_papers)} papers")
    
    return {"type": "papers_found", "count": len(found_papers)}

@agent("ranker", channel="papers", responds_to=["papers_found"])
def rank_papers(spore):
    """Score and rank papers by relevance to the query."""
    found = papers["found"]
    if not found: return
    
    logging.info(f"📊 Ranking {len(found)} papers")
    
    scored = []
    for paper in found:
        try:
            # Simple LLM scoring
            score_text = chat(f"Rate relevance of '{paper['title'][:80]}' to '{papers['query']}' (1-10):", timeout=5.0)
            score = float(score_text.strip())
        except:
            score = 5.0  # Default if LLM fails
        
        scored.append({**paper, "score": score})
    
    # Sort by score and take top 5
    scored.sort(key=lambda p: p["score"], reverse=True)
    papers["ranked"] = scored[:papers["target"]]
    
    logging.info(f"🎯 Top {len(papers['ranked'])} papers selected")
    for i, p in enumerate(papers["ranked"], 1):
        logging.info(f"  {i}. {p['title'][:50]}... (Score: {p['score']:.1f})")
    
    return {"type": "papers_ranked", "count": len(papers["ranked"])}

@agent("downloader", channel="papers", responds_to=["papers_ranked"])
def download_papers(spore):
    """Download the top-ranked papers as PDFs."""
    ranked = papers["ranked"]
    if not ranked: return
    
    Path("downloaded_papers").mkdir(exist_ok=True)
    logging.info(f"📥 Downloading {len(ranked)} papers...")
    
    for i, paper in enumerate(ranked, 1):
        try:
            # Clean filename
            title = re.sub(r'[<>:"/\\|?*]', '', paper['title'][:40])
            filename = f"{i:02d}_{paper['id']}_{title}.pdf"
            
            logging.info(f"  📄 Downloading {i}/{len(ranked)}: {paper['title'][:40]}...")
            
            # Download and save
            response = requests.get(paper['pdf_url'], timeout=20)
            with open(f"downloaded_papers/{filename}", 'wb') as f:
                f.write(response.content)
            
            papers["downloaded"].append({**paper, "filename": filename})
            logging.info(f"    ✅ Saved: {filename}")
            
        except Exception as e:
            logging.error(f"    ❌ Failed: {paper['title'][:30]}... ({e})")
    
    return {"type": "downloads_complete", "count": len(papers["downloaded"])}

@agent("curator", channel="papers", responds_to=["downloads_complete"])  
def show_results(spore):
    """Display final results and save metadata."""
    downloaded = papers["downloaded"]
    if not downloaded: return
    
    logging.info(f"🎉 Download complete! {len(downloaded)}/5 papers")
    
    # Show summary
    print(f"\n📊 Downloaded Papers for: '{papers['query']}'")
    print("=" * 50)
    for i, p in enumerate(downloaded, 1):
        print(f"{i}. 📄 {p['title']}")
        print(f"   👥 {', '.join(p['authors'][:2])}{'...' if len(p['authors']) > 2 else ''}")
        print(f"   🎯 Score: {p['score']:.1f}/10 | 📁 {p['filename']}")
        print()
    
    # Save metadata
    with open("downloaded_papers/metadata.json", 'w') as f:
        json.dump({"query": papers["query"], "papers": downloaded}, f, indent=2)
    
    print(f"📁 All files saved to: downloaded_papers/")

# ==========================================
# SIMPLE ORCHESTRATION FUNCTIONS  
# ==========================================

def start_paper_download(topic: str):
    """Start autonomous paper downloading - simple!"""
    logging.info(f"🚀 Starting paper download for: {topic}")
    
    # Clear state
    papers.update({"found": [], "ranked": [], "downloaded": [], "query": topic})
    
    # Start all agents - this single call starts everything!
    start_agents(
        search_arxiv_papers, rank_papers, download_papers, show_results,
        initial_data={"query": topic, "type": "search_request"},
        channel="papers"
    )

def wait_for_completion(timeout=60):
    """Wait for download to complete."""
    import time
    start_time = time.time()
    
    while len(papers["downloaded"]) < papers["target"] and (time.time() - start_time) < timeout:
        time.sleep(1)
    
    return len(papers["downloaded"]) >= papers["target"]

# ==========================================
# MAIN APPLICATION
# ==========================================

def main():
    """Pythonic arXiv paper downloader demo."""
    print("📚 Pythonic ArXiv Paper Downloader")
    print("   Powered by Praval's Decorator API")
    print("=" * 40)
    print("Simple decorated functions coordinate autonomously!")
    print()
    
    try:
        while True:
            topic = input("📚 Enter research topic (or 'quit'): ").strip()
            if topic.lower() in ['quit', 'exit', 'q']:
                break
            
            if not topic:
                continue
            
            print(f"\n🚀 Starting download for: '{topic}'")
            print("=" * 40)
            
            start_paper_download(topic)
            success = wait_for_completion(timeout=90)
            
            if success:
                print("\n✅ Download completed successfully!")
            else:
                print("\n⏰ Download timed out or failed")
            
            print("=" * 40)
    
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()
