"""Licensed ReportLab Vera fonts; optional administrator-supplied font paths."""
import os
from pathlib import Path
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def register(prefix):
    folder=Path(reportlab.__file__).resolve().parent/'fonts'
    pdfmetrics.registerFont(TTFont(prefix,os.environ.get('KESTREL_PDF_FONT') or str(folder/'Vera.ttf')))
    pdfmetrics.registerFont(TTFont(prefix+'Bold',os.environ.get('KESTREL_PDF_FONT_BOLD') or str(folder/'VeraBd.ttf')))
    return prefix,prefix+'Bold'
