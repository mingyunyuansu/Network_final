#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
这是“多人聊天室及文件共享平台”服务器端的程序serv.py。大体的思路是，有一个监听用的socket，为每一个连接过来的客户创建一个新的socket，并且为该socket创建两个线程。
这两个线程分别是clientThreadIn和clientThreadOut，分别处理进来的数据以及出去的数据，这一点非常类似客户端。
但是要注意，和客户端一样，服务器端也加入了大量的条件判断分支，以进行各种特殊的命令操作。

同时，为了更好地控制线程，服务器端引入了 con = threading.Condition()，这是一个Python的内置方法，该变量用于管理线程锁。具体来讲，就是只有当一个线程处理好了一个数据，通过noyify()方法通知剩下的线程，剩下的线程才能继续工作，这就是生产者-消费者的模式。
注意程序中的NotifyAll()方法，该方法是一个统筹线程的体现，一般情况下，当某线程处理好了数据，便调用这个方法，这个方法会将data置为要传送的数据，然后用python内置方法notifyAll()，让所有线程都得到该数据。
涉及文件接收和传送的部分，最好和clin.py一起对比参看。
"""
import socket
import sys
import threading
import struct
import hashlib
import os
import time

persons = {}# 字典用于存储用户名和端口的键值对，不能出现重复的名字就是用它实现的

con = threading.Condition() # Python内置的Condition，管理线程锁
HOST = raw_input("input the server's ip address: ")  # 指定一个创建服务器用的IP
PORT = 65432
data = '' # 类似客户端，服务器端也有一个由多个线程共同维护的字段，用于保存要发送的信息还有接收的信息

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(10) # 该端口即监听端口
print 'Listening...'


def clientThreadIn(conn, name):
    global data, persons
    while True:
        temp = conn.recv(1024) # 首先接收客户端发过来的信息，再进行各种判别
        if not temp or temp.split(':', 1)[1] == ' !bye':
		# 当客户端发送退出命令时，删除该客户，断开连接，并通知各线程发送该端口断开的消息，之后结束这个线程
            del persons[name]
            conn.close()
            NotifyAll(name + " leaves the room! There are/is " + str(
                (threading.activeCount() + 1) / 2 - 2) + " people left!") # 对所有客户端通知有人离开/还剩多少人
            print data
            return
        if temp.split(':', 1)[1] == ' !howmany':
		# 当用户发送查询命令时，要先获得线程锁，并及时对请求的线程发送人数数据，注意这里并不调用NotifyAll()，因为这里只对请求的客户端负责
            if con.acquire():
                conn.send(str((threading.activeCount() + 1) / 2 - 1) + ' person(s)!')
                con.release()
                continue
        if temp.split(':', 1)[1] == ' !users':
		# 类似上面的，也是只对请求客户端返回用户数据
            if con.acquire():
                conn.send(str(persons.keys()))
                con.release()
                continue
        if temp.split(':', 1)[1].split()[0] == '!ft':
		# 当服务器识别到!ft时，首先需要取得线程锁，并且立即发送SERVOK字段。
            if con.acquire():
                conn.send('SERVOK')
                HEAD_STRUCT = '128sIq32s'
                BUFFER_SIZE = 1024
				# 之后为计算MD5码做一些准备，这是通用的操作，在clin.py中也有用到
                print 'Waiting file from %s...' % name

                info_struct = struct.calcsize(HEAD_STRUCT)
                file_info = conn.recv(info_struct) # 这里要接收客户端发来的文件信息，因为里面包含需要的文件长度信息
                file_name2, filename_size, file_size, md5_recv = struct.unpack(HEAD_STRUCT, file_info)
                file_name = file_name2[:filename_size]
                fw = open(file_name, 'wb')
                recv_size = 0
                print "Receiving data..."
				# 用一个1024大小的缓存接收数据
                while (recv_size < file_size):
                    if (file_size - recv_size < BUFFER_SIZE):
                        file_data = conn.recv(file_size - recv_size)
                        recv_size = file_size
                    else:
                        file_data = conn.recv(BUFFER_SIZE)
                        recv_size += BUFFER_SIZE
                    fw.write(file_data)
				# 接受完成后关闭文件指针，计算MD5
                fw.close()
                print "Accept success!"
                print "Calculating MD5..."
                fw = open(file_name, 'rb')
                md5_cal = hashlib.md5()
                md5_cal.update(fw.read())
                print "  Recevie MD5 : %s" % md5_recv
                print "Calculate MD5 : %s" % md5_cal.hexdigest()
                fw.close()
				# 所有都完成后要释放锁，并且回到循环开始（因为这并不属于循环的正常行为，循环中运行的是不执行任何命令，只群发信息的行为）
                con.release()
				# 注意该分支也是仅对一个客户端负责
                continue
        if temp.split(':', 1)[1].strip() == '!ls':
			# 用户希望获得服务器文件列表，就调用python内置方法，形成字符串发送给单个客户端
            if con.acquire():
                lsList = ''
                for each_file in os.listdir(os.getcwd()):
                    if os.path.isfile(each_file):
                        lsList += str(each_file) + '\t'
                conn.send(lsList)
                con.release()
                continue
        if temp.split(':', 1)[1].split()[0] == '!get':
			# 当服务器检测到下载命令时，同样是立即发送SERVOK字段
            if con.acquire():
                conn.send("SERVOK")
                FILE_NAME = temp.split(':', 1)[1].split()[1] # 取得文件名
                print FILE_NAME
                BUFFER_SIZE = 1024
                FILE_SIZE = os.path.getsize(FILE_NAME) # 用内置方法调用文件
                conn.send(str(FILE_SIZE)) # 发送文件大小，因为待接收的客户端需要知道文件的大小。可参看客户端程序，这时客户端正好准备接收该变量
                fr = open(FILE_NAME, 'rb')
				# 之后是发送程序的通用过程
                send_size = 0
                print "Sending data..."
                time_start = time.time()
                while (send_size < FILE_SIZE):
                    if (FILE_SIZE - send_size < BUFFER_SIZE):
                        file_data = fr.read(FILE_SIZE - send_size)
                        send_size = FILE_SIZE
                    else:
                        file_data = fr.read(BUFFER_SIZE)
                        send_size += BUFFER_SIZE
                    conn.send(file_data)
                time_end = time.time()
                print "Send success!"
                print "Cost %f seconds" % (time_end - time_start)
                fr.close()
                con.release()
				# 释放锁，而且显然的，这依然只对单个客户端负责
                continue
        NotifyAll(temp) # 只有上述的条件分支都没有运行时，才会到达该语句，这说明用户发过来的仅是普通的群发消息，那么就调用NotifyAll方法，让所有线程获得data
        print data


def NotifyAll(mes):
	# 这个方法负责对data的维护，当需要群发消息时，该方法为data赋值，并用内置方法notifyAll通知所有线程
    global data
    if con.acquire():
        data = mes
        con.notifyAll()
        con.release()


def ClientThreadOut(conn, name):
	# 负责群发消息
    global data
    while True:
        if con.acquire():
			# 当获得线程锁并准备好群发时，线程需要等待其他线程已经把数据处理好并通知他（具体来说就是等待data）
            con.wait() # 一旦调用NotifyAll，那么说明数据已处理好，可以群发
            if data:
				# 然后便是群发消息。
                try:
                    conn.send(data)
                    con.release()
                except:
					# 如果消息为空，那么便是出现异常，需要结束线程
                    con.release()
                    return


while 1:
	# 这是程序的主循环，在此不断地接收新连接
    conn, addr = s.accept()
    print 'Connected with ' + addr[0] + ':' + str(addr[1])
    name = conn.recv(1024)# 首先接收客户端的昵称
    while name in persons.keys():
		# 需要保证没有重复的名字，让客户端重新输入
        conn.send('the email %s has been used, use another one!' % name)
        name = conn.recv(1024).split(':', 1)[1][1:]
    persons[name] = conn # 当没有重复后，添加该键值对
    NotifyAll('Welcome ' + name + ' to the room!') # 通知所有的客户端
    print data
    print str((threading.activeCount() + 1) / 2) + ' person(s)!' # 显示当前人数
    conn.send(data)
    threading.Thread(target=clientThreadIn, args=(conn, name)).start()
    threading.Thread(target=ClientThreadOut, args=(conn, name)).start()

# s.close() 服务器并不主动退出，除非手动kill
