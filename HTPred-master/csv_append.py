import csv

def Append(file_name, headers_list, list_of_features, validate=True):
    """
    Append list_of_features to file_name.
    If validate=True, check that len(list_of_features) == len(headers_list) before appending.
    """
    if validate and headers_list is not None:
        if len(list_of_features) != len(headers_list):
            raise ValueError(f"Row length ({len(list_of_features)}) != header length ({len(headers_list)}).")
    with open(file_name, 'a', newline='') as csvfile:
        print("Working")
        writer = csv.writer(csvfile)
        writer.writerow(list_of_features)