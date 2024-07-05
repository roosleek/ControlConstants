# ControlConstants

Мини-библиотека для общения с ControlConstants с помощью python3.

## Установка

```bash
pip install .
```

## Пример использования 

```python3
from ControlConstants import utils, ProtocolCC1, TransportUDP, ManagerControlConstants

config_dict = {
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
         }
    }

if __name__=="__main__":
    # 1) Пример использования UDP совместно с протоколом CC1
    udp = TransportUDP(protocol_class=ProtocolCC1, interface_ip="192.168.1.15")
    
    udp.write(0x404a, 3)
    response = udp.read(0x004a)
    print(f"Ответ в виде объекта: {response}") # Для корректного вывода данных нужно применить маску с рабочими битами
    print(f"Ответ в бинарном виде: {response.to_bytes()}")

    # 2) Пример отправки пакета с установленными полями
    packet = ProtocolCC1(header=0xCCC0, address=0x404a, value=4)
    udp.write_packet(packet) # Эквивалентно udp.write(0x404a, 4)

    # 3) Пример использования инициализированного UDP совместно с конфигурацией на основе XML
    # Загрузка конфигурационного файла
    path_to_config = r"jtagmgmt_memory_for_example.xml"
    config_xml = utils.import_config_from_xml(path_to_config)           # Получения словаря из XML-файла 
    board = ManagerControlConstants(transport=udp, config=config_xml)   # Можно использовать config_dict вместо config_xml
    
    response = board.raw_channel            # Чтение
    print(f"Ответ после чтения: {response}")
    print(f"Доступ к полю ответа: {response.value=:#X}")   

    board.raw_channel = 0x5                 # Запись 
    response = board.raw_channel            # Чтение
    print(f"Доступ к полю ответа после установки значения: {response.value=:#X}") # Эквивалентно board.raw_channel.value
```