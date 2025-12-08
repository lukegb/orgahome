"""Small utility to de-animate animated GIFs."""

import enum
import logging
import sys
from collections.abc import Iterable

logger = logging.getLogger(__name__)


class State(enum.Enum):
    READING_HEADER_AND_LSD = 1
    READING_GCT = 2
    READING_BLOCK_HEADER = 3
    READING_BLOCK = 4
    READING_EXTENSION_BLOCK_TYPE = 5
    READING_EXTENSION_BLOCK_LEN = 10
    READING_EXTENSION_BLOCK = 11
    READING_EXTENSION_SUBBLOCK_LEN = 12
    READING_EXTENSION_SUBBLOCK = 13
    READING_IMAGE_DESCRIPTOR = 6
    READING_LCT = 7
    READING_IMAGE_DATA_HEADER = 8
    READING_IMAGE_DATA = 9
    DONE = 14


class Buffer:
    def __init__(self, iterable: Iterable[bytes]):
        self.next_state(State.READING_HEADER_AND_LSD, 0xD)
        self.extension_block_type = None
        self.extension_block = None
        self.holdback_buffer = []
        self.iterable = iterable

    def __iter__(self) -> Iterable[bytes]:
        for b in self.iterable:
            yield from self.consume(b)
            if self.state == State.DONE:
                return
        # Just send whatever we had left.
        if self.buffer_ptr > 0:
            yield self.buffer[: self.buffer_ptr]

    def consume(self, b: bytes) -> Iterable[bytes]:
        if self.state == State.DONE:
            return
        want_bytes = len(self.buffer) - self.buffer_ptr
        logger.debug(f"consuming - got {len(b)}, want {want_bytes}")
        if len(b) > want_bytes:
            read_bytes = want_bytes
        else:
            read_bytes = len(b)
        read_bytes = min(want_bytes, len(b))
        self.buffer[self.buffer_ptr : self.buffer_ptr + read_bytes] = b[:read_bytes]
        self.buffer_ptr += read_bytes
        if self.buffer_ptr < len(self.buffer):
            return  # Don't have enough bytes yet.
        yield from self.handle_buffer(self.buffer)
        if len(b) > read_bytes:
            # Try to consume again
            yield from self.consume(b[read_bytes:])

    def next_state(self, state: State, size: int) -> None:
        logger.debug(f" -> {state} (want {size})")
        self.state = state
        self.buffer = bytearray(size)
        self.buffer_ptr = 0

    def handle_buffer(self, b: bytearray) -> Iterable[bytes]:
        match self.state:
            case State.READING_HEADER_AND_LSD:
                yield bytes(b)  # output the header/LSD
                # [0:3] 3 byte signature ("GIF")
                # [3:6] 3 byte version ("87a" "89a")
                # [6:8] 2 byte 'logical screen width'
                # [8:a] 2 byte 'logical screen height'
                # [a:b] 1 byte packed fields
                #  - 1b GCT flag
                #  - 3b color res
                #  - 1b sort flag
                #  - 3b size of GCT
                # [b:c] 1 byte Background Color Index
                # [c:d] 1 byte Pixel Aspect Ratio
                gct_info = b[0xA]
                has_gct = (gct_info & 0b10000000) != 0
                if has_gct:
                    gct_len = 3 * (1 << ((gct_info & 0b111) + 1))
                    self.next_state(State.READING_GCT, gct_len)
                else:
                    self.next_state(State.READING_BLOCK_HEADER, 1)
            case State.READING_GCT:
                yield bytes(b)  # output the GCT
                self.next_state(State.READING_BLOCK_HEADER, 1)
            case State.READING_BLOCK_HEADER:
                if b[0] == 0x21:  # Extension Block
                    self.holdback_buffer = [b]
                    self.next_state(State.READING_EXTENSION_BLOCK_TYPE, 1)
                elif b[0] == 0x2C:  # Image Descriptor
                    yield bytes(b)
                    self.next_state(State.READING_IMAGE_DESCRIPTOR, 9)
                else:
                    assert False, f"unknown block type {b[0]}"
            case State.READING_EXTENSION_BLOCK_TYPE:
                self.extension_block_type = b[0]
                logging.debug("extension block %02x", b[0])
                self.extension_block = None
                self.holdback_buffer.append(b)
                if self.extension_block_type == 0xFE:
                    # Comment blocks are sometimes empty, and it's easier
                    # to just treat them as subblocks than deal with it
                    # otherwise.
                    self.next_state(State.READING_EXTENSION_SUBBLOCK_LEN, 1)
                else:
                    self.next_state(State.READING_EXTENSION_BLOCK_LEN, 1)
            case State.READING_EXTENSION_BLOCK_LEN:
                self.holdback_buffer.append(b)
                self.next_state(State.READING_EXTENSION_BLOCK, b[0])
            case State.READING_EXTENSION_BLOCK:
                self.extension_block = b
                self.holdback_buffer.append(b)
                self.next_state(State.READING_EXTENSION_SUBBLOCK_LEN, 1)
            case State.READING_EXTENSION_SUBBLOCK_LEN:
                self.holdback_buffer.append(b)
                if b[0] == 0:
                    # We're done reading this extension block.
                    is_netscape = self.extension_block_type == 0xFF and self.extension_block == b"NETSCAPE2.0"
                    if is_netscape:
                        logging.debug("Discarding NETSCAPE2.0 block")
                    else:
                        # It this wasn't a NETSCAPE2.0 block, then we output it.
                        yield from self.holdback_buffer
                    self.holdback_buffer = []
                    self.extension_block_type = None
                    self.extension_block = None
                    self.next_state(State.READING_BLOCK_HEADER, 1)
                else:
                    self.next_state(State.READING_EXTENSION_SUBBLOCK, b[0])
            case State.READING_EXTENSION_SUBBLOCK:
                self.holdback_buffer.append(b)
                self.next_state(State.READING_EXTENSION_SUBBLOCK_LEN, 1)
            case State.READING_IMAGE_DESCRIPTOR:
                yield bytes(b)
                # Do we have a LCT?
                lct_info = b[8]
                has_lct = (lct_info & 0b10000000) != 0
                if has_lct:
                    lct_len = 3 * (1 << ((lct_info & 0b111) + 1))
                    self.next_state(State.READING_LCT, lct_len)
                else:
                    self.next_state(State.READING_IMAGE_DATA_HEADER, 2)
            case State.READING_LCT:
                yield bytes(b)
                self.next_state(State.READING_IMAGE_DATA_HEADER, 2)
            case State.READING_IMAGE_DATA_HEADER:
                yield bytes(b)
                # This is a bit of a cheat; we either have 1 byte or 2.
                # We just ignore the LZW minimum code size, since we don't need it.
                logging.debug(f"Got {b}")
                next_len = b[-1]
                if next_len > 0:
                    self.next_state(State.READING_IMAGE_DATA, next_len)
                else:
                    # We can stop; we only want a single image, and this
                    # was it.
                    yield b";"
                    self.next_state(State.DONE, 0)
            case State.READING_IMAGE_DATA:
                yield bytes(b)
                self.next_state(State.READING_IMAGE_DATA_HEADER, 1)


class Rechunker:
    def __init__(self, iterable: Iterable[bytes], min_chunk_size: int):
        self.iterable = iterable
        self.min_chunk_size = min_chunk_size

    def __iter__(self) -> Iterable[bytes]:
        buffer = bytearray()
        for chunk in self.iterable:
            buffer.extend(chunk)
            if len(buffer) >= self.min_chunk_size:
                yield bytes(buffer)
                buffer = bytearray()


def deanimate(input_bytes_iter: Iterable[bytes], min_chunk_size: int = 1024) -> Iterable[bytes]:
    return iter(Rechunker(iter(Buffer(input_bytes_iter)), min_chunk_size))


def file_iterable(fn: str) -> Iterable[bytes]:
    with open(fn, "rb") as f:
        while True:
            b = f.read(512)
            if not b:
                return
            yield b


if __name__ == "__main__":
    import os
    import sys

    logging.basicConfig(level=logging.DEBUG)
    for out in deanimate(file_iterable(sys.argv[1])):
        sys.stdout.buffer.write(out)
