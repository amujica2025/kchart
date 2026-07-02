import pandas as pd
from pathlib import Path
from tqdm import tqdm

def analyze_price_files(folder_path, output_file):
    path = Path(folder_path)
    csv_files = list(path.glob("*.csv"))
    
    report_data = []

    print(f"Processing {len(csv_files)} files in {folder_path}...")
    
    for file in tqdm(csv_files, desc="Analyzing files"):
        try:
            # Skip the first 7 rows
            df = pd.read_csv(file, skiprows=7)
            
            # Select only columns that are NOT 'timestamp'
            price_cols = [c for c in df.columns if c != 'timestamp']
            
            for col in price_cols:
                # FIX: Force data to numeric, turning errors/text into NaN
                data = pd.to_numeric(df[col], errors='coerce')
                data = data.dropna()
                
                if data.empty:
                    continue
                
                # Get stats
                start_val = data.iloc[0]
                end_val = data.iloc[-1]
                mean_val = data.mean()
                
                # Calculate absolute drift (Min/Max variation from start)
                diffs = data - start_val
                max_drift_up = diffs.max()
                max_drift_down = diffs.min()
                
                report_data.append({
                    "Filename": file.name,
                    "Asset": col,
                    "Start_Price": start_val,
                    "End_Price": end_val,
                    "Mean_Price": round(mean_val, 2),
                    "Max_Drift_Up": round(max_drift_up, 2),
                    "Max_Drift_Down": round(max_drift_down, 2)
                })
        except Exception as e:
            # We don't want to stop the whole process, just log the error for that file
            print(f"\nSkipped {file.name} due to error: {e}")

    # Export
    output_path = Path(folder_path) / output_file
    summary_df = pd.DataFrame(report_data)
    summary_df.to_csv(output_path, index=False)
    print(f"\nProcessing complete! Report saved to {output_path}")

# --- RUN ---
analyze_price_files(
    folder_path=r"C:\Users\alexm\Downloads\kbot\my-kalshi-app\csv data\match_price_history", 
    output_file='price_summary_report.csv'
)