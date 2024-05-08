from abc import ABC, abstractmethod
from dataclasses import dataclass, astuple
from typing import ClassVar
import socket
import struct
import xml.etree.ElementTree as ET
import numpy as np

class ProtocolABC(ABC):
    """Абстрактный базовый класс для объектов протокола."""
    def __bytes__(self) -> bytes:
        """Преобразовать объект протокола в байты."""
        return self.to_bytes()

    def to_bytes(self) -> bytes:
        """Преобразовать объект протокола в байты с использованием указанного формата и кортежа значений."""
        raise NotImplementedError(f'Абстрактный метод "{__name__}" не реализован!')

    def from_bytes() -> None:
        """Создать объект протокола из байтов с использованием указанного формата."""
        raise NotImplementedError(f'Абстрактный метод "{__name__}" не реализован!')

    def size() -> int:
        """Получить размер объекта протокола в байтах."""
        raise NotImplementedError(f'Абстрактный метод "{__name__}" не реализован!')

class ProtocolBasedDC(ProtocolABC):
    """Базовый класс для реализации, основанной на использовании dataclasses."""
    def __post_init__(self):
        self.to_bytes()

    def __bytes__(self):
        return self.to_bytes()
    
    def to_bytes(self):
        return struct.pack(self._format, *astuple(self))
    
    @classmethod
    def from_bytes(cls, binary: bytes):
        fields = struct.unpack(cls._format, binary)
        return cls(*fields)
    
    @classmethod
    def size(self):
        return struct.calcsize(self._format)
    
class ProtocolBasedNDA(ProtocolABC):
    """Базовый класс для реализации, основанной на использовании numpy."""
    def __init__(self, binary: bytes):        
        self._original = binary
        self._array = np.frombuffer(bytearray(binary), self._dtype)[0]
    
    def to_bytes(self):
        return self._array.tobytes()
    
    @classmethod
    def from_bytes(cls, binary: bytes):
        return cls(binary)
    
    @classmethod
    def size(self):
        return self._dtype.itemsize
    
    def __getattr__(self, field):
        if field.startswith("_"):
            return object.__getattr__(self, field) 
        if not field in self._dtype.names:
            raise ValueError(f'Поле "{field}" отсутствует.')
        return self._array[field]
            
    def __setattr__(self, field, value):
        if field.startswith("_"):
            return object.__setattr__(self, field, value)  
        if not field in self._dtype.names:
            raise ValueError(f'Поле "{field}" отсутствует.')
        self._array[field] = value

    def __str__(self):
        s = ", ".join([f"{field}={self._array[field]}" for field in self._dtype.names])
        return f'{self.__class__.__name__}({s})'
    
    def __repr__(self):
        return self.__str__()

    def get_recarray(self):
        return self._array.view(np.recarray)

    def __getitem__(self, name):
        return self._array[name]

@dataclass
class ProtocolCC1(ProtocolBasedDC):
    header: int   = 0xCCC0  # uint16 | 2 байта
    address: int  = 0       # uint16 | 2 байта
    value: int    = 0       # uint64 | 8 байт
    _format: ClassVar[str] = ">"+"H"+"H"+"Q" 

@dataclass
class ProtocolCC2(ProtocolBasedDC):
    header: int    = 0xCC20 # uint16 | 2 байт
    dev_id: int    = 0      # uint16 | 2 байт
    timestamp: int = 0      # uint32 | 4 байта
    counter: int   = 0      # uint16 | 2 байта
    address: int   = 0      # uint16 | 2 байта
    value: int     = 0      # uint64 | 8 байта
    _format: ClassVar[str] = ">"+"H"+"H"+"I"+"H"+"H"+"Q"

class ProtocolGapSensorStreamRaw(ProtocolBasedNDA):
    _dtype = np.dtype([
        # Служебные данные
        ('header', 'S2'),                   # Заголовок 0x0005                                      | 2 байта
        ('name', 'S3'),                     # Тип пакета в ASCII, для обработанных данных 'raw'     | 3 байта
        ('channel', '>u1'),                 # Номер канала                                          | 1 байт
        ('timestamp', '>u8'),               # Время с момента включения датчика, мкс                | 8 байт
        ('packet', '>u2'),                  # Счетчик пакетов                                       | 2 байта
        # Полезные данные
        ('counts', 'u1', (1408,))           # Первичные данные                                      | 1408 х 1 байт
    ])

class TransportABC(ABC):
    """Абстрактный базовый класс для объектов приемо-передачи пакетов"""

    @abstractmethod
    def write(self, address: int, value: int) -> ProtocolABC or None or int:
        """Записать значение в указанный адрес."""
        pass

    @abstractmethod
    def read(self, address: int) -> ProtocolABC:
        """Считать значение из указанного адреса."""
        pass


class TransportUDP(TransportABC):
    def __init__(self, 
                 protocol_class: ProtocolABC,   # Класс протокола
                 interface_ip: str,             # IP-адрес интерфейса, через который происходит общение с ControlConstants
                 buffer_size: int = None,       # Максимальный размер сообщения (поля data в UDP-посылке); если не указан, берется из протокола
                 tx_ip: str = "192.168.1.255",  # IP-адрес для отправки команд
                 tx_port: int = 32766,          # Порт для отправки команд
                 rx_ip: str = "239.1.2.3",      # IP-адрес для получения ответа
                 rx_port: int = 32767,          # Порт для получения ответа                 
                 timeout: int = 5,              # Таймаут ожидания ответа [сек]
                 is_all_groups: bool = True     # 
    ) -> None:
        '''
        Класс для создания объекта передачи данных через UDP-пакеты.

        Примечение: is_all_groups оставить лучше True, т.к. под Windows мы не можем забиндиться на адрес multicast-группы (https://habr.com/ru/articles/141021/)
        '''

        self._protocol_class = protocol_class
        self._sock = None

        if not buffer_size:
            buffer_size = protocol_class.size()
        
        self.interface_ip = interface_ip
        self.tx_address = (tx_ip, tx_port)
        self.rx_address = (rx_ip, rx_port)
        self.timeout = timeout
        self.buffer_size = buffer_size     

        # Конфигурирование сокета
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if is_all_groups:
            self._sock.bind(('', rx_port))
        else:
            self._sock.bind((rx_ip, rx_port))            
        mreq = struct.pack("4s4s", socket.inet_aton(rx_ip), socket.inet_aton(interface_ip)) 
        self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq) # Подключение к multicast-группе
        self._sock.settimeout(timeout)

        # Вывод информации об объекте
        print("##############################")
        print("Создан объект TransportUDP:")
        print(f"Interface: {self.interface_ip}") 
        print(f"TX: {self.tx_address}")
        print(f"RX: {self.rx_address}")    
        print("##############################")
        

    def write(self, address: int, value: int) -> ProtocolABC:
        packet_request = self._protocol_class(address=address, value=value)
        packet_response = self.write_packet(packet_request)
        return packet_response

    def read(self, address: int) -> ProtocolABC:
        packet_request = self._protocol_class(address=address, value=0)
        packet_response = self.write_packet(packet_request)
        return packet_response

    def write_packet(self, packet: ProtocolABC) -> ProtocolABC:
        self.send(packet.to_bytes())
        buffer_response = self.recv()
        packet_response = self._protocol_class.from_bytes(buffer_response)
        return packet_response

    def send(self, buffer: bytes) -> int:
        return self._sock.sendto(buffer, self.tx_address)

    def recv(self) -> bytes:
        buffer_response = self._sock.recv(self.buffer_size)
        return buffer_response



class ManagerControlConstants():
    CLASS_FIELDS = ("_transport", "_config")

    def __init__(self, transport: TransportABC, config: dict) -> None:
        self._transport = transport
        self._config = config
    
        print("##############################")
        print("ControlConstantsManager создан на основе конфигурационного файла.")
        print("##############################")


    def __getattr__(self, name):
        if name in ManagerControlConstants.CLASS_FIELDS:
            return object.__getattr__(self, name)
        
        settings = self._config[name]

        is_visible = (settings["visible"] == "ENABLE")
        if not is_visible:
            raise ValueError(f'Поле "{name}" не видимо.')

        addr = settings["read_hexcmd"]
        mask = 2**settings["workbits"]-1
        response = self._transport.read(addr)
        response.value &= mask
        return response

    def __setattr__(self, name, value):
        if name in ManagerControlConstants.CLASS_FIELDS:
            return object.__setattr__(self, name, value)

        settings = self._config[name]

        is_visible = (settings["visible"] == "ENABLE")
        is_writeable = (settings["write"] == "ENABLE")
        if not is_visible:
            raise ValueError(f'Поле "{name}" невидимо.')
        if not is_writeable:
            raise ValueError(f'Запись в поле "{name}" запрещена.')
        
        addr = settings["write_hexcmd"]
        mask = 2**settings["workbits"]-1

        if value != (value&mask):
            raise ValueError(f'Недопустимое значение для поля "{name}" ({addr=:#X}, {value=:#X})')
        value &= mask
        self._transport.write(addr, value)


class utils:
    @staticmethod
    def xml_to_dict(filepath):
        tree = ET.parse(filepath)
        root = tree.getroot()

        result_dict = {}

        for param in root.findall('.//param'):
            param_name = param.get('name').replace(' ', '_')
            param_data = {}
            
            for child in param:
                param_data[child.tag] = child.text

            result_dict[param_name] = param_data

        return result_dict
    
    @staticmethod
    def replace_str_to_int(dictionary):
        for field, _ in dictionary.items():
            dictionary[field]["write_hexcmd"] = int(dictionary[field]["write_hexcmd"], base=16)
            dictionary[field]["read_hexcmd"] = int(dictionary[field]["read_hexcmd"], base=16)
            dictionary[field]["workbits"] = int(dictionary[field]["workbits"], base=10)
        return dictionary
    
    @staticmethod
    def import_config_from_xml(filepath):
        config = utils.xml_to_dict(filepath)
        config = utils.replace_str_to_int(config)
        return config
    