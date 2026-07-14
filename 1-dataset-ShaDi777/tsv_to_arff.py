import pandas as pd


def determine_attribute_type(series):
    if pd.api.types.is_bool_dtype(series):
        return 'BOOLEAN'
    if pd.api.types.is_numeric_dtype(series):
        return 'NUMERIC'
    elif pd.api.types.is_object_dtype(series) or pd.api.types.is_categorical_dtype(series):
        unique_values = series.dropna().unique()
        unique_values = [str(val).strip() for val in unique_values]
        if len(unique_values) <= 10:
            return "{" + ",".join(unique_values) + "}"
        else:
            return 'STRING'
    else:
        return 'STRING'


def read_tsv_with_encoding(tsv_file, encoding='windows-1251'):
    with open(tsv_file, 'r', encoding=encoding, errors='replace') as file:
        df = pd.read_csv(file, sep='\t')
    return df


def tsv_to_arff(tsv_file, arff_file, relation_name):
    df = read_tsv_with_encoding(tsv_file, "UTF-8")

    with open(arff_file, 'w', encoding='UTF-8') as f:
        f.write(f"@RELATION {relation_name}\n\n")

        for column in df.columns:
            attribute_type = determine_attribute_type(df[column])
            f.write(f"@ATTRIBUTE {column} {attribute_type}\n")

        f.write("\n@DATA\n")

        for _, row in df.iterrows():
            row_data = []
            for value in row:
                if pd.isna(value):
                    row_data.append('?')
                else:
                    row_data.append(str(value))
            f.write(','.join(row_data) + '\n')


tsv_to_arff('parsed_data.tsv', 'parsed_data.arff', 'Мониторы')
tsv_to_arff('final_data.tsv', 'final_data.arff', 'Мониторы')
