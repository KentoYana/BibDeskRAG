"""Generate small synthetic formats for tests and installed-package smoke checks."""
import io
import struct
import zipfile

def package(parts):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def vint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def pb(*items):
    result = bytearray()
    for number, value in items:
        wire = 0 if isinstance(value, int) else 2
        result.extend(vint((number << 3) | wire))
        result.extend(vint(value) if wire == 0 else vint(len(value)) + value)
    return bytes(result)


def iwa(records):
    raw = b''
    for identifier, kind, payload in records:
        info = pb((1, identifier), (2, pb((1, kind), (3, len(payload)))))
        raw += vint(len(info)) + info + payload
    # Raw Snappy with one literal; exercises long literal encoding too.
    size = len(raw) - 1
    if size < 60:
        tag = bytes([size << 2])
    else:
        width = (size.bit_length() + 7) // 8
        tag = bytes([(59 + width) << 2]) + size.to_bytes(width, 'little')
    block = vint(len(raw)) + tag + raw
    return b'\0' + len(block).to_bytes(3, 'little') + block


def docx(text='RecQ Δset-1'):
    return package({
        'word/document.xml': '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>' + text +
        '</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Table evidence</w:t>'
        '</w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>',
        'word/_rels/document.xml.rels': '<Relationships><Relationship Id="r1" '
        'TargetMode="External" Target="https://example.invalid/do-not-fetch"/></Relationships>',
        'word/media/image.png': b'ignored media',
    })


def pptx():
    def body(text):
        return ('<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                '<a:p><a:r><a:t>' + text + '</a:t></a:r></a:p></p:sld>')
    return package({
        'ppt/presentation.xml': '<p:presentation xmlns:p="http://schemas.openxmlformats.org/'
        'presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/'
        '2006/relationships"><p:sldIdLst><p:sldId r:id="s2"/><p:sldId r:id="s1"/>'
        '</p:sldIdLst></p:presentation>',
        'ppt/_rels/presentation.xml.rels': '<Relationships><Relationship Id="s1" Type="x/slide" '
        'Target="slides/slide1.xml"/><Relationship Id="s2" Type="x/slide" Target="slides/slide2.xml"/>'
        '</Relationships>',
        'ppt/slides/slide1.xml': body('Second slide'),
        'ppt/slides/slide2.xml': body('First slide RecQ'),
        'ppt/slides/_rels/slide2.xml.rels': '<Relationships><Relationship Id="n1" '
        'Type="x/notesSlide" Target="../notesSlides/notesSlide1.xml"/></Relationships>',
        'ppt/notesSlides/notesSlide1.xml': body('Speaker notes'),
    })


def binary_doc(text='RecQ 日本語\rSecond paragraph\r'):
    """Generate a minimal valid CFB with 4K regular streams, no mini-FAT."""
    word = bytearray(4096)
    struct.pack_into('<HH', word, 0, 0xA5EC, 0xC1)
    struct.pack_into('<H', word, 32, 14)
    struct.pack_into('<H', word, 62, 22)
    encoded = text.encode('utf-16le')
    chars = len(encoded) // 2
    struct.pack_into('<I', word, 76, chars)
    struct.pack_into('<H', word, 152, 34)
    pieces = struct.pack('<IIHIH', 0, chars, 0, 512, 0)
    clx = b'\x02' + struct.pack('<I', len(pieces)) + pieces
    struct.pack_into('<II', word, 154 + 33 * 8, 0, len(clx))
    word[512:512 + len(encoded)] = encoded
    table = clx.ljust(4096, b'\0')
    header = bytearray(512)
    header[:8] = bytes.fromhex('d0cf11e0a1b11ae1')
    struct.pack_into('<HHHH', header, 24, 0x3E, 3, 0xFFFE, 9)
    struct.pack_into('<H', header, 32, 6)
    struct.pack_into('<I', header, 44, 1)  # FAT count
    struct.pack_into('<I', header, 48, 1)  # directory sector
    struct.pack_into('<I', header, 56, 4096)
    struct.pack_into('<IIII', header, 60, 0xFFFFFFFE, 0, 0xFFFFFFFE, 0)
    struct.pack_into('<109I', header, 76, 0, *([0xFFFFFFFF] * 108))
    fat = [0xFFFFFFFD, 0xFFFFFFFE] + list(range(3, 10)) + [0xFFFFFFFE]
    fat += list(range(11, 18)) + [0xFFFFFFFE]
    fat += [0xFFFFFFFF] * (128 - len(fat))
    directory = bytearray(512)
    for index, (name, kind, start, size) in enumerate([
        ('Root Entry', 5, 0xFFFFFFFE, 0), ('WordDocument', 2, 2, 4096), ('0Table', 2, 10, 4096),
    ]):
        offset = index * 128
        data = (name + '\0').encode('utf-16le')
        directory[offset:offset + len(data)] = data
        struct.pack_into('<HBB', directory, offset + 64, len(data), kind, 1)
        struct.pack_into('<III', directory, offset + 68, 0xFFFFFFFF,
                         2 if index == 1 else 0xFFFFFFFF, 1 if index == 0 else 0xFFFFFFFF)
        struct.pack_into('<IQ', directory, offset + 116, start, size)
    return bytes(header) + struct.pack('<128I', *fat) + directory + word + table


def binary_xls():
    def record(kind, payload=b''):
        return struct.pack('<HH', kind, len(payload)) + payload
    def bof(kind):
        return record(0x809, struct.pack('<HHHHII', 0x600, kind, 0xDBB, 0x7CC, 0, 6))
    strings = ['gene', 'value', 'RecQ']
    sst = struct.pack('<II', 3, 3)
    for value in strings:
        sst += struct.pack('<HB', len(value), 1) + value.encode('utf-16le')
    sheet_name = 'Genes'
    def bound(offset):
        return record(0x85, struct.pack('<IBBBB', offset, 0, 0, len(sheet_name), 0)
                      + sheet_name.encode())
    prefix = bof(5) + record(0x42, struct.pack('<H', 1200))
    prefix += bound(0) + record(0xFC, sst) + record(0x0A)
    offset = len(prefix)
    prefix = bof(5) + record(0x42, struct.pack('<H', 1200)) + bound(offset)
    prefix += record(0xFC, sst) + record(0x0A)
    sheet = bof(0x10) + record(0x200, struct.pack('<IIHHH', 0, 2, 0, 2, 0))
    for row, col, value in [(0, 0, 0), (0, 1, 1), (1, 0, 2)]:
        sheet += record(0xFD, struct.pack('<HHHI', row, col, 0, value))
    sheet += record(0x203, struct.pack('<HHHd', 1, 1, 0, 42.0)) + record(0x0A)
    return prefix + sheet


def numbers():
    def reference(value):
        return pb((1, value))
    entries = b''.join(pb((3, pb((1, key), (3, text.encode()))))
                       for key, text in enumerate(['gene', 'value', 'RecQ']))
    def cell(index=None, number=None):
        if index is not None:
            return bytes([5, 3]) + b'\0' * 6 + struct.pack('<II', 8, index)
        return bytes([5, 2]) + b'\0' * 6 + struct.pack('<I', 2) + struct.pack('<d', number)
    row_infos = b''
    for index, values in enumerate([(cell(0), cell(1)), (cell(2), cell(number=42))]):
        data = pb((1, index), (6, b''.join(values)),
                  (7, struct.pack('<HH', 0, len(values[0]))))
        row_infos += pb((5, data))
    store = pb((3, pb((1, pb((1, 0), (2, reference(30)))))),
               (4, reference(20)), (9, pb((1, pb((1, 0), (2, 0))))))
    table = pb((4, store), (6, 2), (7, 2), (8, b'Genes'))
    return package({'Index/Document.iwa': iwa([(10, 6001, table),
                    (20, 6005, entries), (30, 6002, row_infos)])})

