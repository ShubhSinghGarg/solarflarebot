# Process sentence into array of acceptable words
def ProcessSentence(width, sentence):
    pWords = []

    for word in sentence.split(' '):
        if len(word) <= (width - 4):
            pWords.append(word)
        else:
            x = word
            while len(x) > (width - 4):
                pWords.append(x[:width - 4])
                x = x[width - 4:] 
            pWords.append(x)

    return pWords
    
# Return a nice, boxed sentence
def BoxedSentence(width, sentence):
    words = ProcessSentence(width, sentence)

    arrays = [
        f''' {'_' * (width - 2)} ''',
        f'''|{' ' * (width - 2)}|'''
    ]
    cRow = ''
    for word in words:
        if len(cRow) + len(word) + 1 <= (width - 4):
            cRow = f'''{cRow} {word}'''.lstrip(' ')
        else:
            arrays.append(f'''| {cRow}{' ' * (width - 4 - len(cRow))} |''')
            cRow = word
    
    arrays.append(f'''| {cRow}{' ' * (width - 4 - len(cRow))} |''')
    arrays.append(f'''|{'_' * (width - 2)}|''')
    
    return arrays

# Return the 3 x 25 meter
def Meter(arrow, answer, closed=True):
    row1 = f''' {' ' * (arrow-1)}V{' ' * (25-arrow)} '''
    row2 = f'''o{'=' * 25}o'''
    if closed:
        row3 = f''' {'?' * 25} '''  
    else:
        row3 = [' '] * 25

        row3[max(0,answer-3)] = '1'
        row3[max(0,answer-2)] = '2'      
        row3[min(24,answer+1)] = '1'
        row3[min(24,answer)] = '2'
        row3[answer-1] = '3'

        row3 = f''' {''.join(row3)} '''

    return [row1, row2, row3]

def FullDisplay(box1, box2, meter):
    height = max(len(box1), len(box2))

    # Pad stuff
    box1 = [(' ' * len(box1[0]))] * (height - len(box1)) + box1
    box2 = [(' ' * len(box2[0]))] * (height - len(box2)) + box2
    meter = [(' ' * len(meter[0]))] * (height - len(meter)) + meter

    return [box1[i] + meter[i] + box2[i] for i in range(height)]

box1 = BoxedSentence(15, 'SOMETHING YOUR FATHER SAY')
box2 = BoxedSentence(15, 'SOMETHING YOUR MOTHER SAY')

print('\n'.join(FullDisplay(box1, box2, Meter(10, 12))))
