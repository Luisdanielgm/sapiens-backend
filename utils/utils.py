from datetime import datetime

def parse_date(date_string):
    formats_to_try = ["%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %Z"]
    for format_str in formats_to_try:
        try:
            date_obj = datetime.strptime(date_string, format_str)
            return date_obj.strftime("%Y-%m-%d")  # Formato final deseado
        except ValueError:
            pass
    return None  # Si ninguno de los formatos funciona