# /home 双 NVMe 分区统一维护方案

**状态：仅保存方案，尚未执行。等待用户晚上明确通知后开始，不设置自动执行任务。**

**目标：** 将 179.223.2.2 的两块 NVMe 统一为 GPT + 单个 Linux LVM 分区，保留 /home 数据、路径、文件系统 UUID 和约 11.6 TiB 容量。

**方法：** 完整备份到系统盘；离线缩小 ext4 和 LV；将剩余有效 LV 迁至第二块盘，腾空第一块盘后重新分区并加入 VG；最后扩回 LV 和文件系统。

**技术：** Ubuntu、ext4、LVM2、GPT、rsync。此文是操作检查单，不是可以直接批量执行的脚本。执行时必须按实时检查结果逐步进行。

## 1. 范围与已核实状态

只调整 **179.223.2.2**，不调整 179.228.2.2，不调整系统盘 /dev/sda。

| 项目 | 当前状态 |
| --- | --- |
| 第一块盘 | /dev/nvme0n1，序列号 RS6U0CB263008VEA，整盘 PV |
| 第一块 PV UUID | 3nvEs2-0UBD-tSdv-ai8B-NnoH-vEfV-4YEQxg |
| 第二块盘 | /dev/nvme1n1，序列号 RS6U0CB263008VDS，已有 GPT |
| 第二块 PV | /dev/nvme1n1p1，UUID QwRi2g-0xLz-Xmnm-qOAY-y4Y9-8pT1-WvelAa |
| 第二块分区边界 | 起始扇区 2048，长度 12502441984 扇区，扇区大小 512 字节 |
| 第二块分区类型 | 当前为通用 Linux filesystem，需改为 Linux LVM，边界不变 |
| 卷组 / 逻辑卷 | vg_home / lv_home，线性卷，约 11.6 TiB，VG 无空闲 extent |
| 文件系统 | ext4，UUID eaeae172-8c34-4fc9-87ef-cfbd27e7faf4，挂载 /home |
| 实际数据 | du 约 131.2 GiB；会在执行前重新统计 |
| 最小尺寸估计 | resize2fs -P 输出 36917542 个 4 KiB 块，约 140.8 GiB；仅作估计 |
| 系统盘空间 | /dev/sda4，df 约 344 GiB 可用；须执行前重新检查 |
| Docker 数据 | /home/docker |
| containerd 数据 | /home/containerd |
| runner 服务 | actions.runner.ascend-catlass-actions.runner-179-223-2-2.service |

当前 LV 的第一段位于 nvme0n1，第二段位于 nvme1n1p1。两块盘容量相同，但分区起始对齐会占用少量空间，最终容量可能比现在少一个或少量 4 MiB extent，不能保证字节数完全相同。

目标布局：

```text
nvme0n1  GPT
└─nvme0n1p1  Linux LVM ─┐
                       ├─ vg_home/lv_home  ext4  /home  约 11.6 TiB
nvme1n1  GPT            │
└─nvme1n1p1  Linux LVM ─┘
```

## 2. 开始条件与维护窗口

1. 收到用户晚上开始维护的明确通知，才开始服务器写操作、备份和停服务。
2. 重新核实盘序列号、PV UUID、LV 分段、文件系统、磁盘健康、数据量和根分区空间。设备名称仅用于定位，不能作为写盘的唯一依据。
3. 确保系统盘可容纳完整备份并保留至少 50 GiB 余量；空间不足则不开始离线操作，先确定其他备份位置。
4. 列出最新 runner 作业、容器和 /home 会话。此前发现运行中的容器 deepep-jimsu7-20261019，以及 yuantao 的 TRAE/AI 和 cann 的 VSCode 会话。晚上必须重新盘点；新增或超出已授权范围的业务中断需先确认。
5. 预留至少一小时窗口，并允许延长。12 TiB ext4 的检查、缩容和迁移耗时取决于文件分布及磁盘性能，不能承诺固定完成时间。
6. 方案本身不需要重启；如内核无法重读分区表而必须重启，先说明原因并取得当次允许。

## 3. 保存状态和制作完整备份

1. 在根文件系统建立带时间戳的状态目录 /var/lib/home-layout-<timestamp> 和数据备份目录 /var/backups/home-layout-<timestamp>/home，确认它们不位于 /home 或其他待调整设备。
2. 保存 pvs/vgs/lvs 的详细输出、VG extent 大小和分段映射、vgcfgbackup、blkid、findmnt、fstab、分区表及必要的磁盘标签/元数据备份。第二块 GPT 同时保存文本和二进制备份。
3. 保存 Docker/containerd 配置、systemd 挂载依赖、runner 服务状态，以及容器 ID、启动方式、原先运行状态和用户会话清单。已有 /var/lib/home-lvm-migration 状态目录保留。
4. 可以先用 rsync -aHAXSx --numeric-ids 做预复制。此时源仍可能变化，不能将预复制视为最终一致备份。
5. 在 runner 空闲后暂停 runner。停止已确认范围内的容器、Docker/containerd 和占用 /home 的开发进程、会话，并控制维护期间的新写入。操作终端工作目录必须位于根文件系统；长操作应从 /home 外的独立控制任务执行，防止断连中断维护。
6. 确认 Docker overlay 等嵌套挂载已退出，再做最终 rsync。只有确认目标是本次新建备份目录时，才可考虑使用 --delete。
7. 用校验和 dry-run 核对静态数据，抽查用户目录、项目、权限、ACL、xattr、硬链接、稀疏文件和 Docker/containerd 数据。备份出错或不完整则停止。

**检查点 A：完整一致备份已验证，停止范围已确认。LVM 元数据备份不能代替文件数据备份。**

## 4. 离线缩小并腾空第一块盘

1. 检查所有 /home 子挂载和使用进程均已退出，正常卸载 /home。禁止强制或 lazy 卸载；仍忙则查清占用后再继续。
2. 对卸载后的 ext4 执行 e2fsck，处理可修复问题；发现不可修复错误则停止。
3. 重新确认最小尺寸和实际数据，选择 **512 GiB** 作为暂时尺寸；若实时数据不再适合该尺寸，则重新计算，不照搬。
4. **先缩 ext4，后缩 LV。** resize2fs 完成后再次检查文件系统，确认实际文件系统字节数不超过预定 LV 大小，才将 LV 缩至 512 GiB。
5. 检查 LV 分段；按当前布局，此时有效 LV 应仅在第一块 PV 上，第二块 PV 应完全空闲。若结果不同，停止并重新设计迁移，不能猜测映射。
6. 将第一块 PV 的剩余 LV extent 全部 pvmove 至第二块分区 PV，等待完成并核实 VG 状态。中断时优先检查并恢复 pvmove，不能直接删除其临时卷。
7. 确认第一块 PV 已分配 extent 为 0、LV 无任何段引用它，才允许进入下一阶段。

**检查点 B：512 GiB 文件系统完整，LV 已完整迁至第二块分区，第一块盘完全无有效 LV extent。**

## 5. 统一分区并扩回容量

1. 再次以序列号、PV UUID 和分段映射核对第一块盘，使用 vgreduce 移除空 PV，再移除其 PV 标签。
2. 只对已腾空的第一块盘创建 GPT 和单分区：起始扇区 2048，结束位置按真实磁盘边界对齐，类型 Linux LVM（GUID E6D6D379-F507-44C2-A23C-238F2A3DF928，sgdisk 类型 8e00）。
3. 核实内核看到的新分区边界，在 /dev/nvme0n1p1 创建新 PV 并加入 vg_home。
4. 将第二块既有分区类型改为 Linux LVM；保留分区起点、长度、分区 UUID 和 PV 内容。绝不在第二块盘重建文件系统或 PV，绝不清空其 GPT。修改前保存 GPT 备份，修改后逐项比较边界。
5. 处理分区表重读时如遇 busy，停止检查设备引用，不能强行继续或自行重启。
6. 确认两块分区 PV 均正常后，将 LV 扩展到 VG 全部可用空间，再扩展 ext4。
7. 再次检查 ext4、UUID、LV 分段和容量，确认 PV 都是分区设备。

**检查点 C：两盘均 GPT + Linux LVM 分区，/home 文件系统完整，容量恢复约 11.6 TiB。**

## 6. 恢复与验收

1. 通过现有 fstab UUID 挂载 /home，保留 vg_home/lv_home 名称和 ext4 UUID。
2. 核对目录内容、权限及备份校验结果，确认 Docker/containerd 路径及 systemd 的 RequiresMountsFor 依赖有效。
3. 按原先状态恢复 containerd、Docker 和原先运行的容器。容器需核实健康、设备挂载及数据，不能一律启动原本停止的容器。
4. 验证普通用户 SSH、sudo、开发目录可访问；交互开发会话由用户重连。
5. 验证 Docker Root Dir 为 /home/docker，containerd root 为 /home/containerd，镜像和容器数据可用。
6. 验证 npu-smi 正常，weekly CANN 和 NPUIR 原有安装路径可访问；恢复 runner 并确认 GitHub 显示在线空闲。
7. 保存最终 lsblk、分区表、pvs/vgs/lvs、df、findmnt 和服务验证结果，交付维护记录。
8. **保留本次完整备份，待用户验收并明确要求后再清理。** 以前“清除备份”的授权不用于自动清除此备份。

## 7. 回退与中止规则

| 所处阶段 | 回退方式 |
| --- | --- |
| 尚未缩 LV | 重新挂载原 /home，恢复原服务状态 |
| 已缩容，尚未改变 PV 成员 | 保持有效的小文件系统，或确认原 VG 正常后依次扩 LV、扩 ext4，再恢复服务 |
| pvmove 已完成，尚未重分区 | LV 已在第二块 PV；可保留临时 512 GiB 容量挂载恢复服务，或检查 VG 后恢复容量 |
| 第一块盘已重分区，新 PV 尚未加入 | 第二块仍保存完整 512 GiB LV；优先保持其有效，修复第一块新 PV 加入步骤，必要时以临时容量恢复服务 |
| 文件系统或校验异常 | 停止写入，保留两块盘、状态记录和完整备份，另行制定恢复步骤 |

不得把旧 vgcfgbackup 盲目恢复到新的 PV 布局；它可能引用已被迁移或覆盖的位置。不得在未确认有效数据已迁出的盘上执行重分区、格式化、wipefs 或 pvcreate。任何检查点不满足都暂停，不跳过。

## 8. 参考

- [Red Hat：将数据迁出物理卷后移除磁盘](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/7/html/logical_volume_manager_administration/disk_remove_ex)
- [Red Hat：管理 LVM 卷组](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/8/html/configuring_and_managing_logical_volumes/managing-lvm-volume-groups_configuring-and-managing-logical-volumes)

以上容量和工作负载是方案编写时的快照。晚上接到通知后先重新检查，再按检查点执行。
