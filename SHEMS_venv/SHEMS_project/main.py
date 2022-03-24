#opzione 1, web server, prosumer_comm, local GUI scrivono su file json che vado a leggere
# MAIN CON TRE CICLI IN MULTITHREAD CHE GIRANO E LEGGONO FILE QUANDO C'è LA CONDIZIONE RICHIAMO DELLE CALLBACK
import json


from Utilities.timer import perpetualTimer

def reading_json_callback():
    fp = open('test.json', 'r')
    file = json.load(fp)
    fp.close()
    print(file)

def reading_json_callback2():
    fp = open('test2.json', 'r')
    file = json.load(fp)
    fp.close()
    print(file)

def reading_json_callback3():
    fp = open('test3.json', 'r')
    file = json.load(fp)
    fp.close()
    print(file)

if __name__ == '__main__':
    t = 1
    test = perpetualTimer(t, reading_json_callback)
    test.start()

    test = perpetualTimer(t, reading_json_callback2)
    test.start()

    test = perpetualTimer(t, reading_json_callback3)
    test.start()