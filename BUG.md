# 问题

## 模型命名错误

player.glb 模型名称是Mesh_<index> 实际输出GLTF_<index>

## 骨骼节点模型引用错误

当前实现把所有网格都塞到节点列表,缺少筛选逻辑.我需要解析场景,节点的网格列表只存在关联模型. 例如player.glb :
{node:"head",model_part:["Mesh_0"]} 

## 配置缺失

把所有通过命令行传参的参数都加入configs里面