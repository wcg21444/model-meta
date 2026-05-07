#include "modelmeta.h"

#include <utility>

namespace GLTFModelMeta {

void to_json(nlohmann::json& j, const BoundingBox& value) {
  j = nlohmann::json::object();
  j["min"] = value.min;
  j["max"] = value.max;
}

void from_json(const nlohmann::json& j, BoundingBox& value) {
  j.at("min").get_to(value.min);
  j.at("max").get_to(value.max);
}

void to_json(nlohmann::json& j, const TextureSlots& value) {
  j = nlohmann::json::object();
  j["base_color"] = value.base_color;
  j["metallic"] = value.metallic;
  j["roughness"] = value.roughness;
  j["normal"] = value.normal;
}

void from_json(const nlohmann::json& j, TextureSlots& value) {
  if (j.contains("base_color") && !j.at("base_color").is_null()) {
    j.at("base_color").get_to(value.base_color);
  }
  if (j.contains("metallic") && !j.at("metallic").is_null()) {
    j.at("metallic").get_to(value.metallic);
  }
  if (j.contains("roughness") && !j.at("roughness").is_null()) {
    j.at("roughness").get_to(value.roughness);
  }
  if (j.contains("normal") && !j.at("normal").is_null()) {
    j.at("normal").get_to(value.normal);
  }
}

void to_json(nlohmann::json& j, const Material& value) {
  j = nlohmann::json::object();
  j["mat_name"] = value.mat_name;
  j["is_pbr"] = value.is_pbr;
  j["textures"] = value.textures;
  j["alpha_mode"] = value.alpha_mode;
  j["roughness"] = value.roughness;
  j["metallic"] = value.metallic;
}

void from_json(const nlohmann::json& j, Material& value) {
  j.at("mat_name").get_to(value.mat_name);
  j.at("is_pbr").get_to(value.is_pbr);
  j.at("textures").get_to(value.textures);
  j.at("alpha_mode").get_to(value.alpha_mode);
  j.at("roughness").get_to(value.roughness);
  j.at("metallic").get_to(value.metallic);
}

void to_json(nlohmann::json& j, const ModelPart& value) {
  j = nlohmann::json::object();
  j["model_name"] = value.model_name;
  j["bounding_box"] = value.bounding_box;
  j["material"] = value.material;
  j["mesh_index"] = value.mesh_index;
}

void from_json(const nlohmann::json& j, ModelPart& value) {
  j.at("model_name").get_to(value.model_name);
  j.at("bounding_box").get_to(value.bounding_box);
  j.at("material").get_to(value.material);
  j.at("mesh_index").get_to(value.mesh_index);
}

void to_json(nlohmann::json& j, const SkeletonNode& value) {
  j = nlohmann::json::object();
  j["node_name"] = value.node_name;
  j["model_part"] = value.model_part;
}

void from_json(const nlohmann::json& j, SkeletonNode& value) {
  j.at("node_name").get_to(value.node_name);
  j.at("model_part").get_to(value.model_part);
}

void to_json(nlohmann::json& j, const ModelMeta& value) {
  j = nlohmann::json::object();
  j["version"] = value.version;
  j["model_type"] = value.model_type;
  j["bounding_box"] = value.bounding_box;
  j["model_part"] = value.model_part;
  j["skeleton"] = value.skeleton;
  j["textures"] = value.textures;
  j["materials"] = value.materials;
}

void from_json(const nlohmann::json& j, ModelMeta& value) {
  j.at("version").get_to(value.version);
  j.at("model_type").get_to(value.model_type);
  j.at("bounding_box").get_to(value.bounding_box);
  j.at("model_part").get_to(value.model_part);
  if (j.contains("skeleton") && !j.at("skeleton").is_null()) {
    j.at("skeleton").get_to(value.skeleton);
  }
  j.at("textures").get_to(value.textures);
  j.at("materials").get_to(value.materials);
}

ModelMeta Parse(const std::string& jsonStr) {
  return nlohmann::json::parse(jsonStr).get<ModelMeta>();
}

} // namespace GLTFModelMeta
