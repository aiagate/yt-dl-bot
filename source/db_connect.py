#! ./.venv/bin/python

# ---standard library---

# ---third party library---

# ---local library---
import sqlite3


class DatabaseConnect(object):
    def __init__(self, db_name):
        self.db = db_name

    def __enter__(self):
        try:
            self.con = sqlite3.connect(self.db)
        except Exception as e:
            self.con = None
            raise e
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.con != None:
            self.con.commit()
            self.con.close()

    def execute(self, sql, *args):
        return self.con.execute(sql, args)

    def create_table(self, tb_name: str, coulumns: str):
        sql = 'CREATE TABLE ' + tb_name + ' (' + coulumns + ')'
        return self.con.execute(sql)

    def insert(self, tb_name: str, values: str):
        sql = 'INSERT INTO ' + tb_name + ' values (' + values + ')'
        self.con.execute(sql)

    def test(self, *args):
        print('test!')


if __name__ == "__main__":
    with DatabaseConnect('databases/chatdata_OqkDihODc2A.db') as db:
        # db.create_table('test', 'id str, title str')
        try:
            id = 'aaa'
            result = db.execute('select min(timestamp) from chatdata')
            # result = db.execute('select timestamp from chatdata')
            # result = db.execute('insert into test values(?,?)',id, 'aaa,bbb) select from')
            # while True:
            #     try:
            #         id = result.fetchone()
            #     except Exception as e:
            #         break
            #     # print(id[0])
            # # print(''.join(  str( result.fetchall() ) ))
            starttime = result.fetchone()[0]
            print(starttime)
            result = db.execute('select message from chatdata where timestamp > ? and timestamp < ?', starttime, starttime + 600000000)
            # print(len(result.fetchall()))
            score_data = []
            for i in result.fetchall():
                score = 0
                # print(i['message'])
                score_word = [
                    '!', '！',
                    '?', '？',
                    'w', 'W','ｗ', 'Ｗ',
                    '草', 
                    ':'
                ]
                if i[0] in score_word:
                    print('hit!')
                    score = score + 1
                score_data.append(score)
            # print(result.fetchall())
            # if result.fetchall() == []:
            #     print(None)
            print(score_data)
        except Exception as e:
            print(e)
