# 模型文件元数据生成器

## 概述

    编写一个python+trimesh脚本,解析gltf 文件,生成指定Scheme的元数据(.meta.json)

## 输出格式

    输出到模型文件的同级目录/<模型名>.modelmeta.json

## 元数据

    "model_type":"skeletal"|"static" //识别模型是否存在骨架骨骼
    "bouding_box":["min":float3,"max":float3] //模型包围盒,用于剔除
    "model_part": [
        {
            "name":<>,
            "bounding_box":<>
            "material":{
                "is_pbr",
                "textures":[
                    "base_color",
                    "metallic(optional)",
                    "roughness(optional)",
                    "normal(optional)",
                ]// 相对路径纹理槽位
                "alpha_mode": "OPAQUE"|"CUTOUT"|"TRANSPARENT",
                "roughness": 0.8,
                "metallic": 0.0
            }
        }
    ]
    "skeleton":[
        {
            "node_name",
            "model_part" :[]

        }
    ]// skeletal文件生成,用于生成物体节点层级架构
