"""Amounts in words for official receipts, e.g. 250.50 -> 'Two hundred fifty pesos and fifty centavos only'."""
from decimal import Decimal, ROUND_HALF_UP

ONES = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve',
        'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
SCALES = [(10 ** 9, 'billion'), (10 ** 6, 'million'), (1000, 'thousand')]


def _under_thousand(n):
    words = []
    if n >= 100:
        words += [ONES[n // 100], 'hundred']
        n %= 100
    if n >= 20:
        words.append(TENS[n // 10] + ('-' + ONES[n % 10] if n % 10 else ''))
    elif n:
        words.append(ONES[n])
    return words


def integer_words(n):
    if n == 0:
        return 'zero'
    words = []
    for value, name in SCALES:
        if n >= value:
            words += _under_thousand(n // value) + [name]
            n %= value
    words += _under_thousand(n)
    return ' '.join(words)


def peso_words(amount):
    amount = Decimal(str(amount or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    pesos, centavos = int(amount), int((amount - int(amount)) * 100)
    text = f"{integer_words(pesos)} peso{'' if pesos == 1 else 's'}"
    if centavos:
        text += f" and {integer_words(centavos)} centavo{'' if centavos == 1 else 's'}"
    return text[0].upper() + text[1:] + ' only'
