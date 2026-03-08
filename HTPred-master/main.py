import time
from os.path import isfile, join, dirname, abspath
from enum import Enum
import sys
import os
import csv
from collections import defaultdict

import getfunctionalfeatures as funf
import string_processing as sp
import features_extractor as f1
import HTPredBenchCreator
import structural_features_extractor as f2
import lfeaturesextractor
import csv_append as ca
import headers_list as hl

'''(Non Trojan = 0, Trojan = 1)'''

# if you run the script from elsewhere, root_dir will be the directory where this script resides
ROOT_DIR = dirname(abspath(__file__))
PARENT_DIR = dirname(ROOT_DIR)   # one level up from the script directory

# Folders (placed next to main.py)
NON_TROJAN_DIR = join(ROOT_DIR, "Non Trojan Files")
TROJAN_DIR = join(ROOT_DIR, "Trojan Files")

CSV_OUTPUT_PATH = join(ROOT_DIR, "data.csv")

# defaults (only for single-run testing)
file_location_input = 's35932_T000_bench.txt'
name_of_file = 's35932_T000_bench.bench'
trojan_nontrojan = 1


def get_raw_list_features(name_of_file):
    columns = defaultdict(list)  # each value in each column is appended to a list

    with open(name_of_file) as f:
        reader = csv.DictReader(f)  # read rows into a dictionary format
        for row in reader:
            for (k, v) in row.items():
                if (k == "Wire"):
                    continue
                columns[k].append(float(v))

    super_list = []
    super_list.append(columns['Controllability0'])
    super_list.append(columns['Controllability1'])
    super_list.append(columns['Observability'])
    super_list.append(columns['Prob0'])
    super_list.append(columns['Prob1'])
    return super_list


def get_feature_data(input_file):
    r = HTPredBenchCreator.BenchToFeature(input_file)
    final_data = r.getfeatures()
    return final_data


def ensure_headers_and_append(csv_path, header_list, feature_row, force_write_headers=False):
    write_headers = False

    if not os.path.exists(csv_path):
        print(f"[INFO] CSV '{csv_path}' does not exist. Will create and write headers.")
        write_headers = True
    else:
        try:
            if os.stat(csv_path).st_size == 0:
                print(f"[INFO] CSV '{csv_path}' exists but is empty. Will write headers.")
                write_headers = True
            else:
                with open(csv_path, 'r', newline='') as fh:
                    reader = csv.reader(fh)
                    try:
                        existing_header = next(reader)
                    except StopIteration:
                        existing_header = []
                if existing_header != [str(h) for h in header_list]:
                    msg = (f"[WARN] Existing CSV header differs from expected header. "
                           f"Existing cols: {len(existing_header)}, Expected cols: {len(header_list)}.")
                    print(msg)
                    if force_write_headers:
                        print("[INFO] force_write_headers=True — rewriting header (will overwrite first row).")
                        write_headers = True
                    else:
                        print("[INFO] Not rewriting header. Appending row anyway (be careful about column mismatch).")
        except Exception as e:
            print("[WARN] Could not inspect existing CSV header:", e)
            write_headers = True

    if write_headers:
        try:
            with open(csv_path, 'w', newline='') as fh:
                writer = csv.writer(fh)
                writer.writerow(header_list)
            print(f"[OK] Wrote header to '{csv_path}' ({len(header_list)} columns).")
        except Exception as e:
            print("[ERROR] Failed to write header:", e)
            return

    try:
        ca.Append(csv_path, header_list, feature_row)
        print(f"[OK] Appended feature row to '{csv_path}'.")
    except Exception as e:
        print("[ERROR] Failed to append feature row via csv_append.Append:", e)


def process_single_file(full_path, filename, label, csv_path=CSV_OUTPUT_PATH, force_write_headers=False):
    """
    Runs the full pipeline for a single bench file.
    full_path: path to the bench text file
    filename: the filename (used when matching functional results)
    label: 0 (non-trojan) or 1 (trojan)
    """
    print("\n" + "=" * 60)
    print(f"Processing file: {filename}  (label={label})")
    print("=" * 60)

    # Turn label to a string (use function param 'label'!)
    trojan_notrojan = str(label)

    try:
        # Step 1 - Functional Features Extraction
        print("---------- Starting Functional Features Extraction -----------")
        funf.getFunctionalfeatures(full_path, trojan_notrojan, filename)
        print("---------- Functional Features Extraction Done -----------")
        print("---------- Results are in functional_results_x folders -----------")

        # Step 2 - String processing
        start_time = time.time()
        print("---------- Starting String Processing -----------")

        # IMPORTANT: use full_path (the file we're processing), not the global sample variable
        (final_gates_list_2,
         final_gates_list,
         super_list_gates,
         mighty_raju_list,
         final_primary_inputs_list,
         final_primary_outputs_list,
         gate_list_input,
         gate_list_output,
         gate_list_name) = sp.StringProcessing(full_path)

        end_time = time.time()
        time_elapsed = end_time - start_time
        print("---------- String processing Done -----------")

        print(f"final_primary_inputs_list: {final_primary_inputs_list}")
        print(f"final_primary_outputs_list: {final_primary_outputs_list}")
        print(f"num gates (approx): {len(final_gates_list)}")
        print("-----------------------------------------------")

        # Step 3 - Get Raw List Features
        print("---------- Starting Getting Raw List Features -----------")

        if (trojan_notrojan == "0"):
            path = join(PARENT_DIR, "functional_results_non_trojan")
        else:
            path = join(PARENT_DIR, "functional_results_trojan")

        files = os.listdir(path)
        raw_feature_list = []
        matched_csv_path = None
        for f in files:
            if (filename in f):
                matched_csv_path = join(path, f)
                raw_feature_list = get_raw_list_features(matched_csv_path)
                break

        if (raw_feature_list == []):
            raise Exception(f'File Functional Feature not found for {filename} in {path} !')

        CC0_list = raw_feature_list[0]
        CC1_list = raw_feature_list[1]
        CO_list = raw_feature_list[2]
        P0_list = raw_feature_list[3]
        P1_list = raw_feature_list[4]

        print("---------- Getting Raw List Features Done -----------")
        print(f"Matched functional CSV file: {matched_csv_path}")

        # Step 4 - Extract Features
        print("---------- Starting Features Extraction -----------")
        list_of_features = f1.FeatureExtractor(final_primary_inputs_list,
                                              final_primary_outputs_list,
                                              final_gates_list,
                                              gate_list_input,
                                              gate_list_output,
                                              gate_list_name,
                                              time_elapsed,
                                              filename,
                                              CC0_list,
                                              CC1_list,
                                              CO_list,
                                              P0_list,
                                              P1_list)
        print("---------- Features Extraction Done -----------")
        print(f"Number of features returned: {len(list_of_features)}")

        # Step 5 - BenchToFeature (structural primitives)
        print("---------- Starting Structural Features (BenchToFeature) -----------")
        structural_data = get_feature_data(full_path)
        print("---------- BenchToFeature Done -----------")

        # Step 6 - Expand structural features
        print("---------- Starting structural_features_extractor.extract_sf (expansion) -----------")
        new_list = f2.extract_sf(structural_data)
        print("---------- structural_features_extractor Done -----------")
        print("Structural feature vector length:", len(new_list))

        list_of_features.extend(new_list)
        print("Structural features appended. Total features now:", len(list_of_features))

        # Step 7 - L-features
        print("---------- Starting L-features extraction (lfeaturesextractor.getLfeatures) -----------")
        Lfeatures = lfeaturesextractor.getLfeatures(CO_list)
        list_of_features.extend(Lfeatures)
        print("L-features appended. Total features now:", len(list_of_features))

        # Step 8 - Append label
        list_of_features.append(trojan_notrojan)
        print("Label appended. Final feature vector length:", len(list_of_features))

        # Final checks and append to CSV
        header_list = hl.Headers()
        print("Header count:", len(header_list))
        if len(header_list) != len(list_of_features):
            print(f"[WARN] header length ({len(header_list)}) != feature vector length ({len(list_of_features)}).")
            print("Mismatch = ", len(list_of_features) - len(header_list))
        else:
            print("[OK] header and feature-vector length match. Appending to CSV.")

        ensure_headers_and_append(csv_path, header_list, list_of_features, force_write_headers=force_write_headers)

        print(f"[SUCCESS] Finished processing {filename}.\n")
        return True, None

    except Exception as e:
        print(f"[ERROR] Processing failed for {filename}: {e}")
        return False, str(e)


def batch_process_all(non_trojan_dir=NON_TROJAN_DIR, trojan_dir=TROJAN_DIR, csv_path=CSV_OUTPUT_PATH,
                      force_write_headers=False):
    summary = {
        "total": 0,
        "processed": 0,
        "failed": 0,
        "failed_files": []
    }

    def _process_folder(folder_path, label):
        nonlocal summary
        if not os.path.isdir(folder_path):
            print(f"[WARN] Folder not found: {folder_path} — skipping.")
            return

        files = sorted(os.listdir(folder_path))
        print(f"\n[INFO] Scanning folder: {folder_path} — found {len(files)} entries.")
        for fname in files:
            fpath = join(folder_path, fname)
            if not os.path.isfile(fpath):
                print(f"[SKIP] {fname} (not a regular file)")
                continue
            if not (fname.endswith(".bench.txt") or fname.endswith(".bench") or fname.endswith(".txt")):
                print(f"[SKIP] {fname} (doesn't match expected bench filename pattern)")
                continue

            summary["total"] += 1
            ok, err = process_single_file(fpath, fname, label, csv_path=csv_path, force_write_headers=force_write_headers)
            if ok:
                summary["processed"] += 1
            else:
                summary["failed"] += 1
                summary["failed_files"].append((fname, err))

    _process_folder(non_trojan_dir, 0)
    _process_folder(trojan_dir, 1)

    print("\n" + "=" * 60)
    print("BATCH PROCESSING SUMMARY")
    print(f"Total files encountered (attempted): {summary['total']}")
    print(f"Successfully processed: {summary['processed']}")
    print(f"Failed: {summary['failed']}")
    if summary['failed_files']:
        print("Failed file list (filename, error):")
        for fn, er in summary['failed_files']:
            print(f" - {fn} : {er}")
    print("=" * 60 + "\n")

    return summary


if __name__ == "__main__":
    batch_process_all(force_write_headers=False)
