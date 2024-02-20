import socket
import struct
from abc import ABC, abstractmethod
import xml.etree.ElementTree as ET


class ControllerABC(ABC):
    @abstractmethod
    def write(self):
        pass

    @abstractmethod
    def read(self):
        pass


class ControllerUDP1(ControllerABC):
    def __init__(self,
                 interface_ip: str,         # IP-адрес интерфейса, через который происходит общение с ContralConstance
                 tx_ip: str = "192.168.1.255", # IP-адрес для отправления команд
                 tx_port: int = 32766,      # Порт для отправления команд
                 rx_ip: str = "239.1.2.3",  # IP-адрес для получения ответа
                 rx_port: int = 32767,      # Порт для получения ответа                 
                 buffer_size: int = 12,     # Размер сообщения (поля data) ContralConstance
                 timeout: int = 2           # Таймаут ожидания ответа [мс]
    ) -> None:
        
        self.IS_ALL_GROUPS = True # Под Windows мы не можем забиндиться на адрес multicast-группы (https://habr.com/ru/articles/141021/)
        
        self.TX_ADDRESS = (tx_ip, tx_port)
        self.RX_ADDRESS = (rx_ip, rx_port)
        self.TIMEOUT = timeout
        self.BUFFER_SIZE = buffer_size     

        if not(interface_ip):
            interface_ip = socket.gethostbyname(socket.gethostname()) # Сравнить с действительным ip-адресом
        self.INTERFACE_IP = interface_ip

        # Конфигурирование сокета
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if self.IS_ALL_GROUPS:
            self.sock.bind(('', rx_port))
        else:
            self.sock.bind((rx_ip, rx_port))            
        mreq = struct.pack("4s4s", socket.inet_aton(rx_ip), socket.inet_aton(interface_ip)) 
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq) # Подключение к multicast-группе
        self.sock.settimeout(timeout)

        # Вывод информации об объекте
        print("###############################")
        print("Создан объект ControllerUDP1:")
        print(f"INTERFACE: {self.INTERFACE_IP}") 
        print(f"TX_ADDRESS: {self.TX_ADDRESS}")
        print(f"RX_ADDRESS: {self.RX_ADDRESS}")    
        print("###############################")

    def write(self, addr: int, value: int) -> bytes:
        payload = self.pack_payload(addr, value)
        self._send(payload)
        return self._recv()

    def read(self, addr: int) -> int:
        payload = self.pack_payload(addr, 0)
        self._send(payload)
        raw = self._recv()
        return self.unpack_payload(raw)[-1]
    
    def _send(self, payload: bytes) -> int:
        return self.sock.sendto(payload, self.TX_ADDRESS)

    def _recv(self) -> bytes:
        return self.sock.recv(self.BUFFER_SIZE)

    def pack_payload(self, addr: int, value: int) -> bytes:
        prefix = 0xccc0
        return struct.pack(">2HQ", prefix, addr, value)  
    
    def unpack_payload(self, msg: bytes) -> tuple:
        return struct.unpack(">2HQ", msg)


class ControlConstantsManager:
    CLASS_FIELDS = ("_controller", "_config_table")
    def __init__(self, controller: ControllerABC, config_table: dict) -> None:
        self._controller = controller
        self._config_table = config_table
        print("###############################")
        print("ControlConstantsManager создан на основе конфигурационного файла.")
        print("###############################")

    def __getattr__(self, name):
        if name in ControlConstantsManager.CLASS_FIELDS:
            return object.__getattr__(self, name)
        
        settings = self._config_table[name]

        is_visible = (settings["visible"] == "ENABLE")
        if not is_visible:
            raise ValueError(f'Поле "{name}" не видимо.')

        addr = settings["read_hexcmd"]
        mask = 2**settings["workbits"]-1
        value = self._controller.read(addr)
        value &= mask
        return value

    def __setattr__(self, name, value):
        if name in ControlConstantsManager.CLASS_FIELDS:
            return object.__setattr__(self, name, value)

        settings = self._config_table[name]

        is_visible = (settings["visible"] == "ENABLE")
        is_writeable = (settings["write"] == "ENABLE")
        if not is_visible:
            raise ValueError(f'Поле "{name}" не видимо.')
        if not is_writeable:
            raise ValueError(f'Поле "{name}" не редактируемо.')
        
        addr = settings["write_hexcmd"]
        mask = 2**settings["workbits"]-1

        if value != (value&mask):
            raise ValueError(f'Недопустимое значение для поля "{name}" (addr=0x{addr:X}, value=0x{value:X})')
        value &= mask
        self._controller.write(addr, value)



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


config_example = {
    "raw_channel": 
         {
             "write_hexcmd": 0x404b,
             "read_hexcmd": 0x004b,
             "write": "ENABLE",
             "visible": "ENABLE",
             "workbits": 3
         },
    "speed_channel":
         {
             "write_hexcmd": 0x404a,
             "read_hexcmd": 0x004a,
             "write": "ENABLE",
             "visible": "ENABLE",
             "workbits": 3
         },
    "thresh_speed_rising":
         {
             "write_hexcmd": 0x4050,
             "read_hexcmd": 0x0050,
             "write": "ENABLE",
             "visible": "ENABLE",
             "workbits": 8
         },
    "switch_control":
         {
             "write_hexcmd": 0x404d,
             "read_hexcmd": 0x004d,
             "write": "ENABLE",
             "visible": "ENABLE",
             "workbits": 1
         }
        }





if __name__=="__main__":
    # Пример использования контроллера
    controller = ControllerUDP1(interface_ip="192.168.1.15")
    controller.write(0x404d, 0x0000)
    print(f"{controller.read(0x004d)=}")

    # Пример использования конфиргурационного файла XML
    xml_filepath = r"D:\Code\PythonExamples\my_libs\jtagmgmt_memory (6).xml"
    config_table = utils.import_config_from_xml(xml_filepath)

    board = ControlConstantsManager(controller=controller, config_table=config_example)
    board.switch_control = 0
    print(f"{board.switch_control=}")



