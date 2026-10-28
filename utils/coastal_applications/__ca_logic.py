from types import SimpleNamespace

CONTENT_CELLS = {'apptitle': (1, 1), 'appdesc': (1, 2), 'appreftitle': (1, 3), 'apprefdesc': (1, 4), 'appTYtitle': (1, 5), 'appTYdesc': (1, 6), 'questiontitle1': (1, 7), 'questiontitle2': (1, 8), 'questiontitle3': (1, 9), 'Qgamertag': (2, 5), 'Qcountry': (2, 6), 'Qage': (2, 7), 'Qgender': (2, 8), 'Qplatform': (2, 9), 'Question1': (2, 10), 'Question2': (2, 11), 'Question3': (2, 12), 'Question4': (2, 13), 'Question5': (2, 14), 'Qrule1': (2, 15), 'Qrule2': (2, 16), 'Qref1': (2, 17), 'Qref2': (2, 18), 'Qref3': (2, 19)}


def load_content(sheet):
    apptitle = sheet.cell(1, 1).value
    appdesc = sheet.cell(1, 2).value
    appreftitle = sheet.cell(1, 3).value
    apprefdesc = sheet.cell(1, 4).value
    appTYtitle = sheet.cell(1, 5).value
    appTYdesc = sheet.cell(1, 6).value
    questiontitle1 = sheet.cell(1, 7).value
    questiontitle2 = sheet.cell(1, 8).value
    questiontitle3 = sheet.cell(1, 9).value
    Qgamertag = sheet.cell(2, 5).value
    Qcountry = sheet.cell(2, 6).value
    Qage = sheet.cell(2, 7).value
    Qgender = sheet.cell(2, 8).value
    Qplatform = sheet.cell(2, 9).value
    Question1 = sheet.cell(2, 10).value
    Question2 = sheet.cell(2, 11).value
    Question3 = sheet.cell(2, 12).value
    Question4 = sheet.cell(2, 13).value
    Question5 = sheet.cell(2, 14).value
    Qrule1 = sheet.cell(2, 15).value
    Qrule2 = sheet.cell(2, 16).value
    Qref1 = sheet.cell(2, 17).value
    Qref2 = sheet.cell(2, 18).value
    Qref3 = sheet.cell(2, 19).value

    pages = [
        {
            "title": questiontitle1 or "Personal Information",
            "questions": [
                ("gamertag", Qgamertag),
                ("country", Qcountry),
                ("age", Qage),
                ("gender", Qgender),
                ("platform", Qplatform),
            ],
        },
        {
            "title": questiontitle2 or "Application Questions",
            "questions": [
                ("question_1", Question1),
                ("question_2", Question2),
                ("question_3", Question3),
                ("question_4", Question4),
                ("question_5", Question5),
            ],
        },
        {
            "title": questiontitle3 or "Rules and References",
            "questions": [
                ("rule_1", Qrule1),
                ("rule_2", Qrule2),
                ("ref_1", Qref1),
                ("ref_2", Qref2),
                ("ref_3", Qref3),
            ],
        },
    ]
    return SimpleNamespace(pages=pages, apptitle=apptitle, appdesc=appdesc, appreftitle=appreftitle, apprefdesc=apprefdesc, appTYtitle=appTYtitle, appTYdesc=appTYdesc, questiontitle1=questiontitle1, questiontitle2=questiontitle2, questiontitle3=questiontitle3, Qgamertag=Qgamertag, Qcountry=Qcountry, Qage=Qage, Qgender=Qgender, Qplatform=Qplatform, Question1=Question1, Question2=Question2, Question3=Question3, Question4=Question4, Question5=Question5, Qrule1=Qrule1, Qrule2=Qrule2, Qref1=Qref1, Qref2=Qref2, Qref3=Qref3)
