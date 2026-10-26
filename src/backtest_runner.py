import json
import os
import sys
import logging
import asyncio
import glob
import time
from gemini_client_backtest import async_call_gemini, build_instruction_dual

# Setup logging
logging.basicConfig(filename='backtest_results.log', level=logging.INFO, format='%(asctime)s - %(message)s', encoding='utf-8')
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

def read_file(path):
    if not os.path.exists(path):
        logging.warning(f"File not found: {path}")
        return ""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Error reading {path}: {e}")
        return ""

async def process_file(data_path, final_instruction, historical_text, idx, total, semaphore, key_index):
    filename = os.path.basename(data_path)
    async with semaphore:
        logging.info(f"[{idx+1}/{total}] Processing {filename}...")
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                current_data = json.load(f)
            
            trade_pairs = current_data.get('trade_pairs', [])
            
            # Call Gemini Async
            result = await async_call_gemini(
                instruction_text=final_instruction,
                current_data=current_data,
                historical_attachment_text=historical_text,
                trade_pairs=trade_pairs,
                image_paths=[],
                key_index=key_index
            )
            
            logging.info(f"Result for {filename}: DONE")
            return {
                "file": filename,
                "result": result
            }
        except Exception as e:
            logging.error(f"Error processing {filename}: {e}")
            return {
                "file": filename,
                "result": f"ERROR: {str(e)}"
            }

async def main_async():
    # Paths
    base_dir = os.getcwd()
    instruction_path = os.path.join(base_dir, "instructions.txt")
    historical_path = os.path.join(base_dir, "price_analysis", "complete_training_dataset.csv")
    
    data_dir = r"c:\Users\derma\Desktop\‏‏‏‏‏‏الاجدد - نسخة - نسخة - نسخة (3)\price_analysis\بيانات"
    start_filename = "combined_snapshots_ADAUSDT_20260209162920.json"
    
    # 1. Get all combined snapshot files
    pattern = os.path.join(data_dir, "combined_snapshots_ADAUSDT_*.json")
    all_files = glob.glob(pattern)
    all_files.sort()
    
    # 2. Find start index
    start_path = os.path.join(data_dir, start_filename)
    try:
        start_index = all_files.index(start_path)
    except ValueError:
        logging.error(f"Start file not found in list: {start_filename}")
        return

    # Load existing results to skip
    existing_results = []
    if os.path.exists("backtest_results_accumulated.json"):
        try:
            with open("backtest_results_accumulated.json", "r", encoding="utf-8") as f:
                existing_results = json.load(f)
                logging.info(f"Loaded {len(existing_results)} existing results.")
        except Exception as e:
            logging.warning(f"Could not load existing results: {e}")
            
    processed_filenames = {item["file"] for item in existing_results if "error" not in item["result"].lower()}
    
    files_to_process = all_files[start_index:]
    files_to_process = [f for f in files_to_process if os.path.basename(f) not in processed_filenames]
    logging.info(f"Resuming backtest. {len(files_to_process)} files remaining (including retries).")
    
    # Remove entries that will be reprocessed from existing_results
    existing_results = [item for item in existing_results if item["file"] in processed_filenames]
    
    instruction_text = read_file(instruction_path)
    historical_text = read_file(historical_path)
    # Limit historical text size
    max_hist_chars = 6000
    if len(historical_text) > max_hist_chars:
        historical_text = historical_text[:max_hist_chars]
        
    final_instruction = build_instruction_dual(instruction_text)
    
    # Semaphore to limit concurrency (reduced to 1 to avoid 429 and allow key rotation)
    semaphore = asyncio.Semaphore(1)
    
    tasks = []
    # Use existing results as base
    results = existing_results
    
    for i, data_path in enumerate(files_to_process):
        tasks.append(process_file(data_path, final_instruction, historical_text, i, len(files_to_process), semaphore, i))
    
    # Run tasks and gather results
    # Process in chunks to save intermediate results
    chunk_size = 5
    
    for i in range(0, len(tasks), chunk_size):
        chunk = tasks[i:i + chunk_size]
        chunk_results = await asyncio.gather(*chunk)
        results.extend(chunk_results)
        
        # Save intermediate results
        with open("backtest_results_accumulated.json", "w", encoding="utf-8") as out:
            json.dump(results, out, indent=2, ensure_ascii=False)
            
        logging.info(f"Saved {len(results)}/{len(all_files[start_index:])} results so far.")
        
        # Add delay between chunks to recover rate limits
        logging.info("Sleeping for 5s to recover rate limits...")
        await asyncio.sleep(5)

    print(f"Batch backtest completed. Processed {len(all_files[start_index:])} files. Results in backtest_results_accumulated.json")

def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
