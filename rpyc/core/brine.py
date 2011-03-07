"""
brine - a simple, fast and secure object serializer for immutable objects,
optimized for small integers [-48..160).
the following types are supported: int, bytes, bool, str, float, str, 
slice, complex, tuple(of simple types), forzenset(of simple types)
as well as the following singletons: None, NotImplemented, Ellipsis
"""
from io import BytesIO
from rpyc.lib.compat import Struct, all


# singletons
TAG_NONE = b"\x00"
TAG_EMPTY_STR = b"\x01"
TAG_EMPTY_TUPLE = b"\x02"
TAG_TRUE = b"\x03"
TAG_FALSE = b"\x04"
TAG_NOT_IMPLEMENTED = b"\x05"
TAG_ELLIPSIS = b"\x06"
# types
TAG_UNICODE = b"\x08"
TAG_LONG = b"\x09"
TAG_STR1 = b"\x0a"
TAG_STR2 = b"\x0b"
TAG_STR3 = b"\x0c"
TAG_STR4 = b"\x0d"
TAG_STR_L1 = b"\x0e"
TAG_STR_L4 = b"\x0f"
TAG_TUP1 = b"\x10"
TAG_TUP2 = b"\x11"
TAG_TUP3 = b"\x12"
TAG_TUP4 = b"\x13"
TAG_TUP_L1 = b"\x14"
TAG_TUP_L4 = b"\x15"
TAG_INT_L1 = b"\x16"
TAG_INT_L4 = b"\x17"
TAG_FLOAT = b"\x18"
TAG_SLICE = b"\x19"
TAG_FSET = b"\x1a"
TAG_COMPLEX = b"\x1b"
IMM_INTS = dict((i, bytes([i + 0x50])) for i in range(-0x30, 0xa0))

I1 = Struct("!B")
I4 = Struct("!L")
F8 = Struct("!d")
C16 = Struct("!dd")

_dump_registry = {}
_load_registry = {}
IMM_INTS_LOADER = dict((v, k) for k, v in IMM_INTS.items())

def register(coll, key):
    def deco(func):
        coll[key] = func
        return func
    return deco

#===============================================================================
# dumping
#===============================================================================
@register(_dump_registry, type(None))
def _dump_none(obj, stream):
    stream.append(TAG_NONE)

@register(_dump_registry, type(NotImplemented))
def _dump_notimplemeted(obj, stream):
    stream.append(TAG_NOT_IMPLEMENTED)

@register(_dump_registry, type(Ellipsis))
def _dump_ellipsis(obj, stream):
    stream.append(TAG_ELLIPSIS)

@register(_dump_registry, bool)
def _dump_bool(obj, stream):
    if obj:
        stream.append(TAG_TRUE)
    else:
        stream.append(TAG_FALSE)

@register(_dump_registry, slice)
def _dump_slice(obj, stream):
    stream.append(TAG_SLICE)
    _dump((obj.start, obj.stop, obj.step), stream)

@register(_dump_registry, frozenset)
def _dump_frozenset(obj, stream):
    stream.append(TAG_FSET)
    _dump(tuple(obj), stream)

@register(_dump_registry, int)
def _dump_int(obj, stream):
    if obj in IMM_INTS:
        stream.append(IMM_INTS[obj])
    else:
        obj = str(obj).encode("ascii")
        l = len(obj)
        if l < 256:
            stream.append(TAG_INT_L1 + I1.pack(l) + obj)
        else:
            stream.append(TAG_INT_L4 + I4.pack(l) + obj)

@register(_dump_registry, bytes)
def _dump_bytes(obj, stream):
    l = len(obj)
    if l == 0:
        stream.append(TAG_EMPTY_STR)
    elif l == 1:
        stream.append(TAG_STR1 + obj)
    elif l == 2:
        stream.append(TAG_STR2 + obj)
    elif l == 3:
        stream.append(TAG_STR3 + obj)
    elif l == 4:
        stream.append(TAG_STR4 + obj)
    elif l < 256:
        stream.append(TAG_STR_L1 + I1.pack(l) + obj)
    else:
        stream.append(TAG_STR_L4 + I4.pack(l) + obj)

@register(_dump_registry, float)
def _dump_float(obj, stream):
    stream.append(TAG_FLOAT + F8.pack(obj))

@register(_dump_registry, complex)
def _dump_complex(obj, stream):
    stream.append(TAG_COMPLEX + C16.pack(obj.real, obj.imag))

@register(_dump_registry, str)
def _dump_unicode(obj, stream):
    stream.append(TAG_UNICODE)
    _dump_bytes(obj.encode("utf8"), stream)

@register(_dump_registry, tuple)
def _dump_tuple(obj, stream):
    l = len(obj)
    if l == 0:
        stream.append(TAG_EMPTY_TUPLE)
    elif l == 1:
        stream.append(TAG_TUP1)
    elif l == 2:
        stream.append(TAG_TUP2)
    elif l == 3:
        stream.append(TAG_TUP3)
    elif l == 4:
        stream.append(TAG_TUP4)
    elif l < 256:
        stream.append(TAG_TUP_L1 + I1.pack(l))
    else:
        stream.append(TAG_TUP_L4 + I4.pack(l))
    for item in obj:
        _dump(item, stream)

def _undumpable(obj, stream):
    raise TypeError("cannot dump %r" % (obj,))

def _dump(obj, stream):
    _dump_registry.get(type(obj), _undumpable)(obj, stream)

#===============================================================================
# loading
#===============================================================================
@register(_load_registry, TAG_NONE)
def _load_none(stream):
    return None
@register(_load_registry, TAG_NOT_IMPLEMENTED)
def _load_nonimp(stream):
    return NotImplemented
@register(_load_registry, TAG_ELLIPSIS)
def _load_elipsis(stream):
    return Ellipsis
@register(_load_registry, TAG_TRUE)
def _load_true(stream):
    return True
@register(_load_registry, TAG_FALSE)
def _load_false(stream):
    return False
@register(_load_registry, TAG_EMPTY_TUPLE)
def _load_empty_tuple(stream):
    return ()
@register(_load_registry, TAG_EMPTY_STR)
def _load_empty_str(stream):
    return ""
@register(_load_registry, TAG_UNICODE)
def _load_unicode(stream):
    obj = _load(stream)
    return obj.decode("utf-8")
@register(_load_registry, TAG_LONG)
def _load_long(stream):
    return _load(stream)

@register(_load_registry, TAG_FLOAT)
def _load_float(stream):
    return F8.unpack(stream.read(8))[0]
@register(_load_registry, TAG_COMPLEX)
def _load_complex(stream):
    real, imag = C16.unpack(stream.read(16))
    return complex(real, imag)

@register(_load_registry, TAG_STR1)
def _load_bytes1(stream):
    return stream.read(1)
@register(_load_registry, TAG_STR2)
def _load_bytes2(stream):
    return stream.read(2)
@register(_load_registry, TAG_STR3)
def _load_bytes3(stream):
    return stream.read(3)
@register(_load_registry, TAG_STR4)
def _load_bytes4(stream):
    return stream.read(4)
@register(_load_registry, TAG_STR_L1)
def _load_bytes_l1(stream):
    l, = I1.unpack(stream.read(1))
    return stream.read(l)
@register(_load_registry, TAG_STR_L4)
def _load_bytes_l4(stream):
    l, = I4.unpack(stream.read(4))
    return stream.read(l)

@register(_load_registry, TAG_TUP1)
def _load_tup1(stream):
    return (_load(stream),)
@register(_load_registry, TAG_TUP2)
def _load_tup2(stream):
    return (_load(stream), _load(stream))
@register(_load_registry, TAG_TUP3)
def _load_tup3(stream):
    return (_load(stream), _load(stream), _load(stream))
@register(_load_registry, TAG_TUP4)
def _load_tup4(stream):
    return (_load(stream), _load(stream), _load(stream), _load(stream))
@register(_load_registry, TAG_TUP_L1)
def _load_tup_l1(stream):
    l, = I1.unpack(stream.read(1))
    return tuple(_load(stream) for i in range(l))
@register(_load_registry, TAG_TUP_L4)
def _load_tup_l4(stream):
    l, = I4.unpack(stream.read(4))
    return tuple(_load(stream) for i in xrange(l))

@register(_load_registry, TAG_SLICE)
def _load_slice(stream):
    start, stop, step = _load(stream)
    return slice(start, stop, step)
@register(_load_registry, TAG_FSET)
def _load_frozenset(stream):
    return frozenset(_load(stream))

@register(_load_registry, TAG_INT_L1)
def _load_int_l1(stream):
    l, = I1.unpack(stream.read(1))
    return int(stream.read(l))
@register(_load_registry, TAG_INT_L4)
def _load_int_l4(stream):
    l, = I4.unpack(stream.read(4))
    return int(stream.read(l))

def _load(stream):
    tag = stream.read(1)
    if tag in IMM_INTS_LOADER:
        return IMM_INTS_LOADER[tag]
    return _load_registry.get(tag)(stream)

#===============================================================================
# API
#===============================================================================
def dump(obj):
    """dumps the given object to a byte-string representation"""
    stream = []
    _dump(obj, stream)
    return b"".join(stream)

def load(data):
    """loads the given byte-string representation to an object"""
    stream = BytesIO(data)
    return _load(stream)

simple_types = frozenset([type(None), int, bool, str, float, bytes, 
    slice, complex, type(NotImplemented), type(Ellipsis)])
def dumpable(obj):
    """indicates whether the object is dumpable by brine"""
    if type(obj) in simple_types:
        return True
    if type(obj) in (tuple, frozenset):
        return all(dumpable(item) for item in obj)
    return False


if __name__ == "__main__":
    x = (b"he", 7, "llo", 8, (), 900, None, True, Ellipsis, 18.2, 18.2j + 13, 
        slice(1,2,3), frozenset([5,6,7]), NotImplemented)
    assert dumpable(x)
    y = dump(x)
    z = load(y)
    assert x == z
    








