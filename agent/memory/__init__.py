from .connection import MemoryConnectionMixin
from .extraction import MemoryExtractionMixin
from .write import MemoryWriteMixin
from .read import MemoryReadMixin

class PostgresMemoryStore(MemoryConnectionMixin, MemoryExtractionMixin, MemoryWriteMixin, MemoryReadMixin):
    pass
