#!/usr/bin/env python3
"""
BodhiECG FalkorDB Graph Database OCR & Ingestion CLI
Demonstrates full pipeline: OCR cascade, template / LLM extraction, entity resolution,
Cypher MERGE query generation, and graph database storage in the terminal.
"""

import sys
import os
import glob
import json
import argparse

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline.orchestrator import pipeline_orchestrator
from graph.falkordb import falkor_client
from common.logger import get_logger

logger = get_logger(__name__)

# ANSI Formatting Helpers
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_banner():
    print(f"\n{CYAN}{BOLD}" + "="*70)
    print("      BODHIECG FALKORDB KNOWLEDGE GRAPH & OCR ENGINE (TERMINAL)       ")
    print("="*70 + f"{RESET}\n")

def print_section(title: str):
    print(f"\n{YELLOW}{BOLD}>>> {title}{RESET}")
    print("-" * 60)

def process_file_pipeline(file_path: str, domain_key: str = None):
    print(f"\n{BOLD}Processing File:{RESET} {file_path}")
    if domain_key:
        print(f"{BOLD}Target Domain Schema:{RESET} {domain_key}")
    
    if not os.path.exists(file_path):
        print(f"\033[91mError: File '{file_path}' does not exist.\033[0m")
        return

    # STEP 1: Running Pipeline Orchestrator
    print_section("STEP 1: OCR Cascade & Stage Pipeline Execution")
    ctx = pipeline_orchestrator.process_document(file_path, domain=domain_key)
    
    print(f"Document ID: {GREEN}{ctx.document_id}{RESET}")
    print(f"Status: {GREEN}{ctx.status}{RESET}")
    print(f"Domain Detected: {CYAN}{ctx.domain}{RESET}")
    if ctx.ocr_result:
        print(f"OCR Engine Used: {GREEN}{ctx.ocr_result.engine_used}{RESET}")
        txt_preview = ctx.ocr_result.full_text or ctx.ocr_result.normalized_text or ""
        print(f"Text Preview:\n{CYAN}{txt_preview[:250]}...{RESET}\n")

    # STEP 2: Extracted Knowledge Objects
    print_section("STEP 2: Knowledge Extraction & Entity Alignment")
    print(f"{BOLD}Extracted Fields:{RESET}")
    for k, v in ctx.extracted_fields.items():
        print(f"  • {BOLD}{k}{RESET}: {v}")

    print(f"\n{BOLD}Knowledge Objects ({len(ctx.knowledge_objects)}):{RESET}")
    for obj in ctx.knowledge_objects[:10]:
        print(f"  • [{GREEN}{obj.entity_type}{RESET}] id={BOLD}{obj.canonical_id}{RESET} | props={obj.properties}")

    # STEP 3: Graph Nodes and Relationships
    print_section("STEP 3: Generated Canonical Graph Schema")
    print(f"Graph Nodes Count: {GREEN}{len(ctx.graph_nodes)}{RESET}")
    for node in ctx.graph_nodes[:10]:
        print(f"  • ({GREEN}:{node.label}{RESET} id={node.id} {node.properties})")

    print(f"Graph Edges Count: {GREEN}{len(ctx.graph_edges)}{RESET}")
    for edge in ctx.graph_edges[:10]:
        print(f"  • ({edge.from_label}:{edge.from_id}) -[{MAGENTA}{edge.type}{RESET}]-> ({edge.to_label}:{edge.to_id})")

    # STEP 4: Ingestion Verification
    print_section("STEP 4: FalkorDB Persistence & Verification")
    if ctx.warnings:
        print(f"{YELLOW}Warnings/Validation Issues ({len(ctx.warnings)}):{RESET}")
        for w in ctx.warnings:
            print(f"  [!] {w}")
    else:
        print(f"{GREEN}[OK] Document fully processed and merged into FalkorDB Knowledge Graph!{RESET}")

def run_batch(category: str, max_count: int):
    print_section(f"RUNNING BATCH INGESTION FOR '{category}' (Max {max_count} files)")
    
    base_data = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))
    target_dir = os.path.join(base_data, category)
    
    if not os.path.exists(target_dir):
        print(f"\033[91mError: Target directory '{target_dir}' not found.\033[0m")
        return

    files = glob.glob(os.path.join(target_dir, "*.jpg")) + glob.glob(os.path.join(target_dir, "*.png"))
    files = files[:max_count]

    domain_key = None
    if "bill" in category.lower():
        domain_key = "medical_bill"
    elif "discharge" in category.lower():
        domain_key = "discharge_summary"
    elif "invoice" in category.lower():
        domain_key = "invoice"

    print(f"Found {len(files)} files to process in {target_dir}")
    
    for idx, fpath in enumerate(files, 1):
        print(f"\n[{idx}/{len(files)}] Processing {os.path.basename(fpath)}...")
        process_file_pipeline(fpath, domain_key)

def main():
    print_banner()

    parser = argparse.ArgumentParser(description="BodhiECG FalkorDB Terminal Graph Engine")
    parser.add_argument("-i", "--input", nargs="+", help="One or multiple image/PDF file paths to ingest")
    parser.add_argument("-d", "--domain", default=None, choices=["invoice", "medical_bill", "discharge_summary"], help="Domain schema template")
    parser.add_argument("-b", "--batch", help="Run batch processing on a subfolder in data/ (e.g. 'Invoice', 'Medical/bills')")
    parser.add_argument("-n", "--count", type=int, default=3, help="Max files for batch mode")

    args = parser.parse_args()

    if args.input:
        for fpath in args.input:
            process_file_pipeline(fpath, args.domain)
        return

    if args.batch:
        run_batch(args.batch, args.count)
        return

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sample_invoice = os.path.join(project_root, "data/Invoice/batch1-0001.jpg")
    sample_medical_bill = os.path.join(project_root, "data/Medical/bills/med_doc_bill_100001_noisy.jpg")

    print(f"{YELLOW}No CLI arguments passed. Running interactive terminal demonstration...{RESET}\n")
    
    if os.path.exists(sample_invoice):
        print(f"{BOLD}Demo 1: Commercial Invoice Image Pipeline{RESET}")
        process_file_pipeline(sample_invoice, "invoice")

    if os.path.exists(sample_medical_bill):
        print(f"\n{'='*70}\n")
        print(f"{BOLD}Demo 2: Medical Bill Image Pipeline{RESET}")
        process_file_pipeline(sample_medical_bill, "medical_bill")

    print(f"\n{GREEN}{BOLD}[OK] Terminal Pipeline Execution Complete!{RESET}\n")

if __name__ == "__main__":
    main()
