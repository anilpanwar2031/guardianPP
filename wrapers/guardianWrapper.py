
from Utilities.pdf_utils import *
import pdfplumber
import tabula
import pandas as pd
from PyPDF2 import PdfReader

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from FileDownload import Downloader
import random, string


def getAllTexts(file_path):
    texts = ' '
    with open(file_path, 'rb') as file:
        # Create a PdfReader object
        pdf = PdfReader(file)

        for page in pdf.pages:
            text = page.extract_text()
            texts = texts + text + ' '
    return texts


def getRemarks(texts, claimnumber):
    remarks = ''
    remarks = texts.split(f"Remarks for claim # {claimnumber}:")[1]

    if '10 Hudson' in remarks:
        remarks = remarks.split('10 Hudson')[0]
    if 'SCHEDULE' in remarks:
        remarks = remarks.split('SCHEDULE')[0] + 'SCHEDULE'
    if 'Comments' in remarks:
        remarks = remarks.split('Comments:')[0]

    return remarks.replace('\n', ' ').replace("  ", " ").strip()


def getBenefit(texts, claimnumber):
    benefit = texts.split(f"Remarks for claim # {claimnumber}:")[0]
    benefit_dict = {}
    if 'Remarks for claim' in benefit:
        benefit = benefit.split('Remarks for claim')[1]

    adjustments = '$' + benefit.split('ADJUSTMENTS')[1].split('TOTAL BENEFIT PAID')[0].replace('\n', '').split('$')[1]

    benefit_dict['PaidByOtherInsurance'] = '$' + \
                                           benefit.split('PAID BY OTHER INSURANCE')[1].split('ADJUSTMENTS')[0].replace(
                                               '\n', '').split('$')[1]
    benefit_dict['TotalBenefitPaid'] = '$' + benefit.split('TOTAL BENEFIT PAID')[1].split('PATIENT')[0].replace('\n',
                                                                                                                '').split(
        '$')[1]
    benefit_dict['TotalPatientResp'] = '$' + benefit.split('PATIENT')[1].split('TOTALS\nTOTAL BENEFIT')[0].replace('\n',
                                                                                                                   '').split(
        '$')[1].strip()
    benefit_dict['TotalBenfitPayable'] = benefit.split('PAID BY OTHER INSURANCE')[0].split('\n')[-2].strip()
    benefit_dict['HigherAllowable'] = '$' + \
                                      benefit.split('BENEFIT SUMMARY')[1].split('HIGHER ALLOWABLE')[0].replace('\n',
                                                                                                               '').split(
                                          '$')[1].strip()
    return benefit_dict, adjustments


def process_tabula_address(tabula_df: pd.DataFrame) -> str:
    col_name: str = tabula_df.columns[0]
    item: str = f"{col_name} {' '.join(tabula_df[col_name].to_list())}"
    return item


def other_details(file_path):
    tabula_dfs = tabula.read_pdf(file_path, guess=False, pages=1, stream=True, encoding="utf-8",
                                 area=(97, 288, 152, 570), multiple_tables=True)
    string_to_find = "Provider"
    a = 0
    for key, value in tabula_dfs[0].items():
        if string_to_find in str(key) or string_to_find in str(value):
            a = 1
    if a:
        tab = tabula_dfs[0]
    else:
        tabula_dfs = tabula.read_pdf(file_path, guess=False, pages=2, stream=True, encoding="utf-8",
                                     area=(96, 287, 153, 572), multiple_tables=True)
        tab = tabula_dfs[0]

    df = tab
    df = df.T.reset_index()
    df.columns = df.iloc[0]
    dit = df[1:].reset_index(drop=True).to_dict(orient='records')[0]
    other_dict = {}
    other_dict['Provider'] = dit['Provider:']
    other_dict['RenderingProvider'] = dit['Provider:']
    other_dict['EFT_CheckDate'] = dit['Date:']
    other_dict['EFT_CheckNumber'] = dit['Check No.:']
    other_dict['TotalAmount'] = dit['Payment Amount:']

    return other_dict


def get_basic_details(file_path):
    tabula_dfs = tabula.read_pdf(file_path, guess=False, pages=1, stream=True, encoding="utf-8",
                                 area=[(141, 43, 176, 217), (25, 90, 53, 213), (97, 288, 152, 570)],
                                 multiple_tables=True)
    # y1, x1, y2, x2
    payee_address = process_tabula_address(tabula_dfs[0])
    payee_address_details = extract_address_details(payee_address)

    add_col = tabula_dfs[1]
    payer_add = tabula_dfs[1]
    payer_address = process_tabula_address(payer_add)
    payer_address_details = extract_address_details(payer_address)
    other_info = other_details(file_path)

    master_dict = {
        "Payer": payer_address_details.get("Item", ""),
        "PayerName": 'Guardian',
        "PayerAddress": payer_address_details.get("AddressElements", ""),
        "PayerCity": payer_address_details.get("PlaceName", ""),
        "PayerState": payer_address_details.get("StateName", ""),
        "PayerZip": payer_address_details.get("ZipCode", ""),
        "Payee": payee_address_details.get("Item", ""),
        "PayeeName": payee_address_details.get("ItemName", ""),
        "PayeeAddress": payee_address_details.get("AddressElements", ""),
        "PayeeCity": payee_address_details.get("PlaceName", ""),
        "PayeeState": payee_address_details.get("StateName", ""),
        "PayeeZip": payee_address_details.get("ZipCode", ""),
    }
    master_dict = {**master_dict, **other_info}
    return master_dict


def get_master_details(file_path, texts, url):
    with pdfplumber.open(file_path) as pdf:
        patients = []
        for page in pdf.pages:
            tables = page.extract_tables()
            t = 1
            for table in tables:

                t += 1
                r = 1
                for row in table[:-1]:
                    r += 1
                    if 'Claim Number' in row[0]:
                        patient_dict = {}
                        text = row[0]
                        claimnumber = text.split('Claim Number: ')[1].split(' ')[0]
                        patientaccountno = text.split('Patient Account No.:')[1].split(' ')[0]
                        plannumber = text.split('Plan Number:')[1].split(' ')[0].split('\n')[0]
                        patientname = text.split('Patient Name: ')[1].split('Employee Name')[0].strip()
                        employeename = text.split('Employee Name: ')[1].split('Relationship')[0].strip()
                        relationship = text.split('Relationship: ')[1].split('Planholder:')[0].replace('\n', '')
                        planholder = text.split('Planholder: ')[1]

                        patient_dict['SubscriberID'] = ''
                        patient_dict['PatientName'] = patientname
                        patient_dict['Relationship'] = relationship
                        patient_dict['ClaimId'] = claimnumber
                        patient_dict['PatientAccount'] = patientaccountno
                        patient_dict['PlanNumber'] = plannumber
                        patient_dict['SubscriberName'] = employeename
                        patient_dict['PlanType'] = planholder
                        patient_dict['TransactionFee'] = '$0.00'
                        patient_dict['url'] = url
                        patient_dict['PayerClaimID'] = ''
                        patient_dict['TotalAmount'] = ''
                        patient_dict['ClaimStatus'] = 'Processed'
                        patient_dict['RenderingProvider'] = ''
                        payee_address_details = get_basic_details(file_path)
                        notes = getRemarks(texts, claimnumber)
                        patient_dict.update(payee_address_details)
                        patient_dict['PayerClaimID'] = claimnumber
                        patient_dict['Notes'] = notes
                        benefit, adjustments = getBenefit(texts, claimnumber)
                        patient_dict.update(benefit)
                        patient_dict['PayeeTaxID'] = ''
                        patient_dict['PayerContact'] = '(800) 541-7846'
                        patient_dict['PayerID'] = ''
                        patient_dict['PaymentMethodCode'] = ''
                        patient_dict['RecordID'] = str(uuid.uuid4())
                        patient_dict['RenderingProviderID'] = ''

                        patients.append((patient_dict))

    pl = len(patients)
    indexlist = []
    for i in range(pl):
        try:
            for j in range(i + 1, pl + 1):
                try:
                    if patients[i]["ClaimId"] == patients[j]["ClaimId"]:
                        indexlist.append(j)
                except:
                    pass
        except:
            pass

    indexlist.sort(reverse=True)

    for index in indexlist:
        del patients[index]

    return patients


def benfi(texts, a):
    pass


def remove_duplicate_dict(data_list):
    unique_dicts = list(set(map(lambda x: tuple(sorted(x.items())), data_list)))
    if len(unique_dicts) < len(data_list):
        return [dict(t) for t in unique_dicts]
    else:
        return data_list


def get_claimnumber(eobclaimmaster):
    claims = []
    for i in range(len(eobclaimmaster)):
        claims.append(eobclaimmaster[i]['ClaimId'])
    return claims

def extract_text_coordinates(file_path):
    text_list = []
    with pdfplumber.open(file_path) as pdf:
        # Iterate through each page of the PDF
        for page_number in range(len(pdf.pages)):
            page = pdf.pages[page_number]
            page_number = page_number + 1
            # Extract the text content and its coordinates
            for element in page.extract_words(x_tolerance=1, y_tolerance=1, keep_blank_chars=True):
                text_dict = {}
                text = element["text"]
                x, y = element["x0"], element["top"]

                text_cord = f"Page {page_number + 1}: Text: {text} Coordinates: X={x}, Y={y}"
                text_dict.update({'page': page_number, 'text': text, 'cordx': x, 'cordy': y})
                text_list.append(text_dict)
    return text_list
def get_details(file_path, texts, eobclaimmaster):
    claims = get_claimnumber(eobclaimmaster)
    print("CLAIMS ", claims, len(claims))
    text_list = extract_text_coordinates(file_path)
    pdf_path = file_path
    dfs = []
    x2 = 0
    y2 = 0
    for text_d in text_list:
        x = text_d['cordx']
        y = text_d['cordy']
        if x2 < x:
            x2 = text_d['cordx']
        if y2 < y:
            y2 = text_d['cordy']
    x2 = x2 + 20
    y2 = y2 + 20
    print("YYYY", y2)
    for i in range(len(text_list)):
        x1 = y1 = ''
        if 'Line' in text_list[i]['text']:
            # print("Line", text_list[i]['text'])
            x1 = text_list[i]['cordx']
            y1 = text_list[i]['cordy']
            page_number = text_list[i]['page']
            for j in range(i, len(text_list)):

                if page_number == text_list[j]['page']:
                    if 'BENEFIT SUMMARY' in text_list[j]['text']:
                        # print("Bene", text_list[j]['text'])
                        # print("PAG", text_list[j]['page'])
                        page = int(text_list[j]['page'])
                        y2 = text_list[j]['cordy']
                        # print(f"x1 = {x1}, y1 = {y1}, x2 = {x2}, y2 = {y2}")
                        tabula_dfs = tabula.read_pdf(pdf_path, guess=False, pages=page, stream=True, encoding="utf-8",
                                                     area=(y1, x1, y2, x2), multiple_tables=True)
                        df_filled = tabula_dfs[0].fillna('')
                        dfs.append(df_filled[1:])
                        break

                if page_number == text_list[j]['page']:
                    if '10 Hudson Yards' in text_list[j]['text']:
                        # print("10 Hudson", text_list[j]['text'])
                        # print("PAG", text_list[j]['page'])
                        page = int(text_list[j]['page'])
                        y2 = text_list[j]['cordy']
                        # print(f"x1 = {x1}, y1 = {y1}, x2 = {x2}, y2 = {y2}")
                        tabula_dfs = tabula.read_pdf(pdf_path, guess=False, pages=page, stream=True, encoding="utf-8",
                                                     area=(y1, x1, y2, x2), multiple_tables=True)
                        df_filled = tabula_dfs[0].fillna('')
                        dfs.append(df_filled[1:])
                        break

                if page_number == text_list[j]['page']:
                    #                 if 'BENEFIT SUMMARY' not in text_list[j]['text'] and '10 Hudson Yards' not in text_list[j]['text']:
                    if 'VNE' in text_list[j]['text']:
                        y2 = 780
                        page = int(text_list[j]['page'])
                        # print(f"x1 = {x1}, y1 = {y1}, x2 = {x2}, y2 = {y2}")
                        tabula_dfs = tabula.read_pdf(pdf_path, guess=False, pages=page, stream=True, encoding="utf-8",
                                                     area=(y1, x1, y2, x2), multiple_tables=True)
                        df_filled = tabula_dfs[0].fillna('')
                        dfs.append(df_filled[1:])
                        break

        search_string = 'TOTALS'
        final = []
        stack_list = []
        for d in dfs:
            last_row = d.iloc[-1]
            col = last_row[4]

            # print(col)
            # print(type(col))
            if 'TOTALS' in col:
                print("In the if")
                if stack_list:
                    new_df = pd.concat(stack_list + [d], axis=0)
                    final.append(new_df)
                    stack_list = []
                else:
                    final.append(d)
            else:
                stack_list.append(d)

        tdfs = []

        for df in final:
            df = df[~df.apply(lambda row: row.astype(str).str.contains('TOTALS', case=False)).any(axis=1)]
            df.rename(columns={'Date of': 'Date'}, inplace=True)
            df.fillna('', inplace=True)
            df.drop('Line', axis=1, inplace=True)
            tdfs.append(df)

        new_dict = []
        for i, td in enumerate(tdfs):
            cm = claims[i]
            tab = td.to_dict(orient='records')
            # tab.update({"Enrollee_ClaimID":cm})
            for i in range(len(tab)):
                tab[i].update({"Enrollee_ClaimID": cm})
                new_dict.append(tab[i])

        tab_dict = []

        change_keys = [("Alt", "AltCode"), ("Tooth", "ToothNo"), ("Date", "ServiceDate"),
                       ("Submitted.1", "SubmittedCharges"),
                       ("Benefit", "PayableAmount"), ("Considered", "ActualAllowed"),
                       ("Deductible", "ContractualObligations"), ("Covered", "CoveredCharge"),
                       ("Coverage", "CoveragePercent")]
        for d in new_dict:
            for k in change_keys:
                old_key = k[0]
                new_key = k[1]
                value = d[old_key]
                d[new_key] = value

            proccode = d['Submitted'].split('/')[0]
            description = d['Submitted'].split('/')[-1]

            d.update({'ProcCode': proccode, 'Description': description, 'PatientResp': '', 'Adjustments': '',
                      'OtherAdjustments': '', 'RemarkCodes': '', 'PayerInitiatedReductions': '',
                      "EFT_CheckNumber": eobclaimmaster[0]['EFT_CheckNumber']})

            for k in change_keys:
                del d[k[0]]
            del d['Submitted']
            print("D", d)
            tab_dict.append(d)

    return tab_dict


def getEftPatients(eobclaimmaster):
    eftpatientlist = []
    for p in eobclaimmaster:
        eftpatient_dict = {
            "SubscriberID": "",
            "ProviderClaimId": '',
            "PayerClaimId": p['ClaimId'],
            "MemberNo": p['PatientAccount'],
            "RenderingProviderFirstName": p['Provider'].split(' ')[0].strip(),
            "RenderingProviderLastName": p['Provider'].split(' ')[-1].strip(),
            "PatientName": p['PatientName'],
            "PatientFirstName": p['PatientName'].split(' ')[0].strip(),
            "PatientLastName": p['PatientName'].split(' ')[-1].strip(),
            "PlanType": p['PlanType'],
            "PlanNumber": p['PlanNumber'],
            "RenderingProviderID": "",
            "PayerPaid": p['TotalAmount'],
            "RecordID": str(uuid.uuid4()),
            "PPTransPayorListID": "27e7c674-051c-40ec-b9ef-6c84f3a3dd1d",
            "ClientId": "",
            "EligibilityVerificationId": "44",
            "EFT_CheckNumber": p['EFT_CheckNumber']
        }
        eftpatientlist.append(eftpatient_dict)
    return eftpatientlist


def filedownload_(url):
    """
    To download pdf from blob url
    Args:
        url:
    Returns:
        filepath of pdf
    """
    file_path = (
            "".join(random.choices(string.ascii_uppercase + string.digits, k=10)) + ".pdf"
    )
    print(file_path)
    input_file = url.replace("%20", " ")

    Downloader("Payment Processing", file_path, input_file)

    return file_path


def main(data):
    url = data["EFTPatients"][0]["url"]

    print("main 1")
    file_path = filedownload_(url.replace("%20", " "))
    print("FILEPATHHHHHHHHH", file_path)
    texts = getAllTexts(file_path)
    eobclaimmaster = get_master_details(file_path, texts, url)
    eobclaimdetail = get_details(file_path, texts, eobclaimmaster)
    eftpatients = getEftPatients(eobclaimmaster)

    json_data = {
        'EFTPatients': eftpatients,
        'PpEobClaimMaster': eobclaimmaster,
        'PpEobClaimDetail': eobclaimdetail
    }

    return json_data

