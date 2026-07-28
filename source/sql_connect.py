#! ./.venv/bin/python
# -*- coding: utf-8 -*-

# ---standard library---

# ---third party library---
import mysql.connector
# from mysql.connector.connection_cext import CMySQLConnection
# from mysql.connector.cursor_cext import CMySQLCursor

# ---local library---
import property

class DatabaseConnect(object):
    def __init__(self, db_name):
        self.db = db_name

    def __enter__(self):
        try:
            # self.cnx: CMySQLConnection = mysql.connector.connect(host=property.SQL_HOST, user=property.SQL_USER, password=property.SQL_PASSWD, database=self.db)
            self.cnx = mysql.connector.connect(host=property.SQL_HOST, user=property.SQL_USER, password=property.SQL_PASSWD, database=self.db, use_pure=True)
            # self.cursor: CMySQLCursor = self.cnx.cursor()
            self.cursor = self.cnx.cursor(buffered=True)
        except Exception as e:
            self.cnx = None
            raise e
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.cnx != None:
            self.cnx.commit()
            self.cursor.close()
            self.cnx.close()

    def execute(self,*args):
        return self.cursor.execute(args)

    def create_table(self, tb_name: str, coulumns: str):
        sql = 'CREATE TABLE ' + tb_name + ' (' + coulumns + ')'
        return self.cursor.execute(sql)

    def insert(self, tb_name: str, values: str):
        sql = 'INSERT INTO ' + tb_name + ' values (' + values + ')'
        self.cursor.execute(sql)

if __name__ == "__main__":
    with DatabaseConnect('youtube_chat') as db:
        # db.create_table('test', 'id str, title str')
        try:
            # result = db.execute(property.DATABASE_PATH)
            # result = db.execute('select timestamp from chat_data')
            # result = db.execute('insert into test values(?,?)',id, 'aaa,bbb) select from')
            # while True:
            #     try:
            #         id = result.fetchone()
            #     except Exception as e:
            #         break
            db.execute('show TABLES;')
        except Exception as e:
            print(e)
