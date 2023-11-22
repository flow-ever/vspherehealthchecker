# vspherehealthchecker
a tools for gathering &amp; display vsphere information

# 功能介绍
该工具主要用于收集vSphere的信息，收集的信息主要包含：
- vCenter Server Appliance 虚拟机的运行状况
- vCenter Server下datacenter、Cluster、Host、Virtual machine的配置信息、资源消耗、性能指标等
将收集的信息进行web展示，并对关键信息进行标记，如超出阈值的指标的警示等。
# 适用范围
仅适用于具有vCenter Server管理的vSphere环境
目前该版本仅在vSphere 7.0U3环境下测试通过
# 如何工作
1. 程序启动后，将运行一个Web服务器
2. 用户在数据收集的页面，填写相关凭据
3. 提交信息之后，程序在后台通过远程的方式连接vSphere环境，开始数据采集
4. 采集的数据将以json或者log的文件格式，保存到“data”目录（和程序文件在同一目录）
![Alt text](image.png)
5. 数据采集完毕之后，程序将读取数据文件，然后将采集到的数据展现到web页面
# 使用方法
## 下载程序
vSphereCollector.exe 

## 运行程序
双击运行程序，将出现命令行窗口，运行期间，保持该窗口打开
![Alt text](image-1.png)
## 登录web页面
在web浏览器输入：http://127.0.0.1:9999,进入数据采集页面
![Alt text](image-2.png)
## 开始数据收集
填写完毕信息，点击“Submit”按钮之后，开始数据采集，采集过程中，页面下方将滚动显示采集进度
取决于vSphere环境主机和虚拟机的数量，整个采集过程将持续几分钟到十几分钟。
![Alt text](image-3.png)
采集完毕之后，将自动跳转到数据展示页面
## 展示数据
web页面上面是蓝色导航条
导航条之下：
1. 左侧是vSphere的树形清单，用于导航
2. 右侧是信息展示区
### VCSA虚拟机信息展示
- 文件系统状态展示（红色标注部分：空间使用率过高）
- 各类证书状态展示（红色标注部分：证书将要或者已经过期）
![Alt text](image-4.png)

- vCenter Server各项服务运行状态展示（红色标注部分：服务处于“停止“状态）
![Alt text](image-5.png)
- VCSA虚拟机root用户的状态
![Alt text](image-6.png)
- vCenter上的各类报警
![Alt text](image-7.png)
### Datacenter数据中心展示
在左侧导航条点击某个”Datacenter“，将在右侧展示区通过树形图展示该数据中心的层次结构
![Alt text](image-8.png)
### Cluster群集展示
在左侧导航条点击某个”Cluster“，将在右侧展示区显示该Cluster的相关信息
- 主机信息
- HA、DRS、EVC的配置信息
![Alt text](image-9.png)
- 如果该Cluster启用了VSAN，则展示VSAN信息，包括VSAN的磁盘足够成
![Alt text](image-10.png)
- VSAN的IOPS、Throughput、latency、cache使用情况等信息
![Alt text](image-11.png)
![Alt text](image-12.png)
- VSAN的健康测试结果
![Alt text](image-13.png)
### Hosts主机展示
- 在左侧导航条点击某个”Host“，将在右侧展示区显示该host的相关信息，包含：
- 主机安装的ESXi版本，硬件信息（制造商、SN、Model等）
- 资源使用情况
- 存储相关（相关的datastore、存储控制器、多路径、lun）
![Alt text](image-14.png)
- 网络（标准交换机、PNIC、VNIC）
![Alt text](image-15.png)
- 时间同步情况
- 证书状态
![Alt text](image-16.png)
- 主机上运行的虚拟机的一览（可点击虚拟机展示详细配置）
![Alt text](image-17.png)
### VM虚拟机展示
通过Datacenter树形结构虚拟机链接，以及Host上的虚拟机的链接都可以进入虚拟机详细展示页面
如果虚拟机开机情况下，会展示虚拟机的平均CPU使用率、CPU Reday时间占比，以及虚拟机硬盘的延迟
![Alt text](image-18.png)
![Alt text](image-19.png)
以及虚拟机其他参数配置
![Alt text](image-20.png)
虚拟机磁盘和网络配置
![Alt text](image-21.png)
### 虚拟机信息汇总
统计所有的虚拟机。通过蓝色导航条”虚拟机汇总“进入
- 虚拟机开关机情况
- 虚拟机VMware tools安装情况
- 虚拟机Guest OS分布
- 分配vCPU最多的10台虚拟机（可点击查看柱状图进入虚拟机详细展示页面）
![Alt text](image-22.png)
- 分配内存最多的10台虚拟机（可点击查看柱状图进入虚拟机详细展示页面）
- 实际占用空间最大的10台虚拟机（可点击查看柱状图进入虚拟机详细展示页面）
- Provisioned空间最大的10台虚拟机（可点击查看柱状图进入虚拟机详细展示页面）
- 快照空间占用最大的10台虚拟机（可点击查看柱状图进入虚拟机详细展示页面）
![Alt text](image-23.png)