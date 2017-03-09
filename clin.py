#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
这是“多人聊天室及文件共享平台”的客户端程序（clin.py），以Python2.7版本写成。
本程序主要使用了多线程的处理方法。具体来说，有两个线程：DealOut，DealIn，如其名，一个用来处理由客户端发出数据的工作，一个负责数据的接收。

当程序启动时，首先指定自己的昵称，并输入服务器的IP地址，之后便创建Socket尝试连接。
一旦连接成功，DealOut和DealIn便一直工作，直到异常断开或用!bye命令手动退出。

程序工作时类似QQ群，每个人可以发送消息，且每个人的发出的消息将同时在所有客户端显示。实现是靠两个线程同时维护inString, outString两个字符串。

同时程序具有一些特殊的命令行功能，当输入这些特殊命令时将产生特殊操作，服务器只对发出命令的客户端响应，对其他用户来说察觉不到。

所有的命令都以'!'开头，主要是查询和服务器的上传下载功能，具体有：
!bye:               客户端断开连接
!howmany:           查询当前有多少用户，服务器将返回当前人数
!users:             查询当前的用户列表，即所有人的昵称
!ls:                查询当前服务器端的文件目录
!get [file name]:   从服务器下载某文件到本地
!ft:                传输文件（file transportation）指令，输入指令后将开始指定文件名，输入文件名成功后可将文件上传到服务器
"""
import socket
import threading
import struct
import os
import time
import hashlib

# inString变量是客户端从程序接受的数据，如果是文本，那么直接显示，否则可能是一些标志语句（比如SERVOK，表示服务器已经做好文件传输准备）。
inString = ''
# outString变量是将要从客户端发往服务器的数据，一般为文本，也就是本客户端发的消息，但是也有可能包含标志语句，比如!bye就是退出
outString = ''
# name是本客户端指定的昵称
name = ''
# 以下是判别用的变量，当对应的事件发生时，变量置为真，那么线程中的条件判断会执行相应操作
isexit = False # 判断是否要退出
isft = False # 判断是否要上传文件
servok = False # 判断服务器是否做好准备（一般是通过服务器发回SERVOK语句来判断）
isget = False # 判断是否要下载文件

file_size = 0 # 用来记录文件大小的变量，当指定要下载文件的文件名后，由服务器端返回该文件的大小


def DealOut(s):
	# 本线程负责处理一切发送出去的数据，比如需要发送的文本，或者需要发送的文件数据。
    global name, outString, servok, isft, isget, file_size
    global isexit
    while True:
        outString = raw_input() # 首先接收输入一段话
		
		# 然后是一系列检测，根据命令行功能，如果出现相应的字段，则判别变量置为真
        if outString == '!bye':
            isexit = True
        if outString == '!ft':
            isft = True
        if outString.split()[0] == '!get':
            isget = True

		# 这是通用字段，将输入的字段加上自己的名字后发送给服务器，否则会进一步在条件分支中做处理
        outString = name + ': ' + outString
        s.send(outString)
		
		# 如果要退出，那么关闭连接，跳出线程
        if isexit:
            s.close()
            break
		
		# 如果是要上传文件（注意!ft是file transportation，是上传，!get是下载）
        if isft:
            BUFFER_SIZE = 1024 # 这是发送端的缓存大小
            FILE_NAME = raw_input(
                'Entre the file name: \n')  # 输入文件名
            FILE_SIZE = os.path.getsize(FILE_NAME) # 取得文件大小
			
			# 以下是计算文件的MD5的办法，可根据文件的结构计算一个唯一的特征值，当发送端和接收端的计算结果一致时，说明传输无误
            HEAD_STRUCT = '128sIq32s'  # Structure of file head
            # Calculate MD5
            print "Calculating MD5..."
            fr = open(FILE_NAME, 'rb')
            md5_code = hashlib.md5()
            md5_code.update(fr.read())
            fr.close()
            print "Calculating success"

            # Need open again
            fr = open(FILE_NAME, 'rb')
            # Pack file info(file name and file size)
            file_head = struct.pack(HEAD_STRUCT, FILE_NAME, len(FILE_NAME), FILE_SIZE, md5_code.hexdigest())

			# 当!ft字段发送给服务器端并且无误后，服务器端将返回一个SERVOK字段，这个字段的处理在DealIn线程中，DealIn线程负责把servok字段置为真
            if servok:
				# file_head不仅包含了文件大小，也包含了文件的结构信息，可以给服务器端计算MD5码
                s.send(file_head)
                send_size = 0
                print "Sending data..."
                time_start = time.time()# 计算所花时间
				# 下面是发送文件的过程，就是读入缓存，发送的过程。顺便一提，这是在Unix编程实验中学到的
                while (send_size < FILE_SIZE):
                    if (FILE_SIZE - send_size < BUFFER_SIZE):
                        file_data = fr.read(FILE_SIZE - send_size)
                        send_size = FILE_SIZE
                    else:
                        file_data = fr.read(BUFFER_SIZE)
                        send_size += BUFFER_SIZE
                    s.send(file_data)
                time_end = time.time()
                print "Send success!"
                print "MD5 : %s" % md5_code.hexdigest()
                print "Cost %f seconds" % (time_end - time_start)
                fr.close() # 关闭文件读取的引用
                isft = False # 两个传输过程中所用的判别变量要初始化
                servok = False
                continue


def DealIn(s):
	# 如上所言，本线程负责处理一切接收的数据，比如别的客户端发送的数据（本质上还是服务器发过来的），或者是!get [file name]下载服务器上的文件时，负责接收文件。
    global inString, isexit, isft, servok, isget, file_size
    while True:
		# 一般来讲，如果没有发生各种判别事件，那么本线程的工作就是不断接收客户端发来的文本，并打印在客户端，也就是条件分支外的部分。
        if isget and servok:
			# 这是!get [file name]下载文件时，会进入的分支，当客户端输入!get [file name]，并且服务器返回“SERVOK”字段，那么这两个变量都为真
            file_name = outString.split(':', 1)[1].split()[1]
			# 需要注意，要下载的文件名是由客户端在输入命令时就直接指定的
            BUFFER_SIZE = 1024
			# 以下非常类似发送的过程，只不过一切改为接收，并且文件的大小需要服务器端传过来，保存在file_size中
            file_size = int(s.recv(1024))
            fw = open(file_name, 'wb')
            recv_size = 0
            print "Receiving data..."
            while (recv_size < file_size):
                if (file_size - recv_size < BUFFER_SIZE):
                    file_data = s.recv(file_size - recv_size)
                    recv_size = file_size
                else:
                    file_data = s.recv(BUFFER_SIZE)
                    recv_size += BUFFER_SIZE
                fw.write(file_data)
            fw.close()
            print "Accept success!"

            fw.close()
			# 传输完成后，各种判别变量初始化
            isget = False
            servok = False
            file_size = 0
            continue

        inString = s.recv(1024) # 如果没有进入上述分支，那么会执行这条普通的接收语句，不过该语句同时负责接收SERVOK来对服务器的状态进行判断
        if not inString or isexit:
            break
        if inString == 'SERVOK':
            servok = True
        print inString
    s.close()

# 以下是程序的开始，输入昵称及服务器地址，创建socket
name = raw_input("input your name: ")
ip = raw_input("input the server's ip adrress: ")
# ip = 'localhost'
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((ip, 65432))
sock.send(name)

# 两个线程开始
thin = threading.Thread(target=DealIn, args=(sock,))
thin.start()
thout = threading.Thread(target=DealOut, args=(sock,))
thout.start()

# sock.close()
