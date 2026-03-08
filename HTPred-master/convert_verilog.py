# convert_verilog.py
# Batch convert .v files in "Verilogs Trojan" and "Verilogs Non Trojan"
# into bench files placed into "Trojan Files" and "Non Trojan Files" respectively.
#
# Usage: adjust cell_dir if needed, then run:
#    python convert_verilog.py

import time
import os
import sys
from os.path import dirname, abspath, join

# import the Creator wrapper from HTPredBenchCreator (try both styles)
try:
    from HTPredBenchCreator import Creator
except Exception:
    import HTPredBenchCreator as HBC
    Creator = getattr(HBC, "Creator")

# Root folder (script directory)
ROOT_DIR = dirname(abspath(__file__))

# ----- CONFIG (change paths if you put folders elsewhere) -----
CELL_DIR = join(ROOT_DIR, "tsmc_cells") + os.sep     # cell mapping folder (optional)
SRC_TROJAN_DIR = join(ROOT_DIR, "Verilogs Trojan")   # source verilog trojan files (.v)
SRC_NON_TROJAN_DIR = join(ROOT_DIR, "Verilogs Non Trojan")  # source verilog non-trojan files (.v)

OUT_TROJAN_DIR = join(ROOT_DIR, "Trojan Files")      # where to write .bench for trojan verilog
OUT_NON_TROJAN_DIR = join(ROOT_DIR, "Non Trojan Files")  # where to write .bench for non-trojan verilog

# Optional: top module to pass to Creator (None lets Creator decide)
TOP_MODULE = None
# ---------------------------------------------------------------

def convert_one(verilog_path, cell_dir, top_module=None):
    """Convert a single verilog file and return bench text (or raise)."""
    start = time.time()
    # Creator expects a string top-module name in this repo version; use 'top' as fallback
    used_top = top_module if top_module is not None else 'top'
    print(f"[INFO] Converting: {verilog_path}  (top_module={used_top})")
    # Create Creator and convert
    c = Creator(verilog_path, cell_dir, used_top)
    bench_text = c.convert()
    elapsed_ms = int((time.time() - start) * 1000)
    print(f"[OK] Conversion finished in {elapsed_ms} ms for {os.path.basename(verilog_path)}")
    return bench_text

def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)

def process_folder(src_dir, out_dir, label_name):
    """
    src_dir: folder containing .v files
    out_dir: folder where .bench files will be written
    label_name: string used in prints ("Trojan" / "Non Trojan")
    """
    print(f"\n[INFO] Scanning {label_name} verilog folder: {src_dir}")
    if not os.path.isdir(src_dir):
        print(f"[WARN] Source folder not found: {src_dir} — skipping {label_name}.")
        return

    ensure_dir(out_dir)
    files = sorted(os.listdir(src_dir))
    vfiles = [f for f in files if f.lower().endswith(".v")]
    print(f"[INFO] Found {len(vfiles)} .v files in {src_dir}.")

    for fname in vfiles:
        src_path = join(src_dir, fname)
        base = os.path.splitext(fname)[0]
        bench_name = base + ".bench"
        out_path = join(out_dir, bench_name)

        if os.path.exists(out_path):
            print(f"[SKIP] bench version already existing for {fname}, skip")
            continue

        # Not found -> convert
        print(f"[NEW] new verilog file that doesnt have its bench version detected : {fname}. starting conversion")
        try:
            bench_text = convert_one(src_path, CELL_DIR, top_module=TOP_MODULE)
            # write bench into out_dir
            with open(out_path, "w", newline="\n", encoding="utf-8") as fh:
                fh.write(bench_text)
            print(f"[DONE] conversion done, {bench_name} has been put inside {os.path.basename(out_dir)} folder")
        except Exception as e:
            print(f"[ERROR] Conversion failed for {fname}: {e}")

def main():
    # Warn if Creator import failed earlier (should've thrown already)
    print(f"[INFO] Root dir: {ROOT_DIR}")
    if not os.path.isdir(CELL_DIR):
        print(f"[WARN] cell_dir not found: {CELL_DIR} (converter may still work without it)")

    # Process Trojan then Non-Trojan
    process_folder(SRC_TROJAN_DIR, OUT_TROJAN_DIR, label_name="Trojan")
    process_folder(SRC_NON_TROJAN_DIR, OUT_NON_TROJAN_DIR, label_name="Non Trojan")

    print("\n[INFO] All done.\n")

if __name__ == "__main__":
    main()