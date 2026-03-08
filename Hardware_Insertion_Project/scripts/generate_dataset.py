import os
import subprocess
import shutil
import time

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
BUILD_DIR = PROJECT_ROOT  # Assuming main.exe is in root
INPUT_DIR = os.path.join(PROJECT_ROOT, "inputs")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "dataset")

# Configuration
EXECUTABLE = os.path.join(BUILD_DIR, "bin", "trojan_framework.exe")
BENCHMARKS = [
    "c2670", "c3540", "c5315", "c6288",
    "s1423", "s13207", "s15850"
]
PAYLOAD_TYPES = {
    1: "XOR",
    2: "Delay",
    3: "DoS_1",
    4: "Leak"
}
TRIGGER_SIZES = [2, 4] # We can expand this

def run_generation(bench_path, trig_size, payload_type):
    """
    Runs the C++ interactive tool via subprocess, sending inputs to stdin.
    """
    if not os.path.exists(EXECUTABLE):
        print(f"Error: Executable not found at {EXECUTABLE}")
        return False

    # Inputs for interactive menu:
    # 1. Trigger Size
    # 2. Payload Type
    input_str = f"{trig_size}\n{payload_type}\n"
    
    try:
        process = subprocess.Popen(
            [EXECUTABLE, bench_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=PROJECT_ROOT
        )
        stdout, stderr = process.communicate(input=input_str)
        
        if "Values saved to:" in stdout:
            return True, stdout
        else:
            return False, stdout
    except Exception as e:
        return False, str(e)

def main():
    print("Starting Dataset Generation...")
    
    # Create dataset directory structure
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    clean_dir = os.path.join(OUTPUT_DIR, "clean")
    trojan_dir = os.path.join(OUTPUT_DIR, "trojan")
    
    if not os.path.exists(clean_dir): os.makedirs(clean_dir)
    if not os.path.exists(trojan_dir): os.makedirs(trojan_dir)

    # Walk through inputs
    for root, dirs, files in os.walk(INPUT_DIR):
        for file in files:
            if file.endswith(".bench"):
                bench_name = os.path.splitext(file)[0]
                if bench_name not in BENCHMARKS: continue
                
                src_path = os.path.join(root, file)
                
                # Copy clean file
                shutil.copy(src_path, os.path.join(clean_dir, file))
                
                # Create circuit-specific trojan folder
                circ_trojan_dir = os.path.join(trojan_dir, bench_name)
                if not os.path.exists(circ_trojan_dir):
                    os.makedirs(circ_trojan_dir)
                
                print(f"\nProcessing {bench_name}...")
                
                # Generate Variants
                for q in TRIGGER_SIZES:
                    for p_type, p_name in PAYLOAD_TYPES.items():
                        # We can generate multiple variants per config if we want
                        # But main.exe currently overwrites or creates one output.
                        # Output of main.exe is: inputs/subdir/bench_trojan.bench (usually)
                        # Or it saves to the path specified in processFile?
                        # main.cpp:104 fs::path outP = fs::path(outputDir) / filename;
                        # processFile(entry.path, outDir) where outDir = outputs/subdir
                        # Wait, main.cpp:114 calls processFile(argv[1], ".") -> current dir
                        
                        # So it will create bench_trojan.bench in PROJECT_ROOT
                        
                        success, log = run_generation(src_path, q, p_type)
                        
                        if success:
                            # Move and rename
                            # Default output name from main.cpp:103 is stem + "_trojan.bench"
                            generated_file = os.path.join(PROJECT_ROOT, f"{bench_name}_trojan.bench")
                            
                            if os.path.exists(generated_file):
                                new_name = f"{bench_name}_Tj_{p_name}_q{q}.bench"
                                dest_path = os.path.join(circ_trojan_dir, new_name)
                                shutil.move(generated_file, dest_path)
                                print(f"  [SUCCESS] Generated {new_name}")
                            else:
                                print(f"  [FAIL] Output file not found for {bench_name} q={q} p={p_type}")
                        else:
                            # If it failed (e.g. no cliques), log it
                            if "No cliques" in log:
                                print(f"  [SKIP] No cliques of size {q} for {bench_name}")
                            else:
                                print(f"  [ERROR] Failed for {bench_name} q={q} p={p_type}")

    print("\nDataset Generation Complete!")
    print(f"Dataset location: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
