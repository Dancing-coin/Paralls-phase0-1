shader_type spatial;
render_mode blend_add, depth_draw_opaque, cull_disabled, unshaded, fog_disabled;

uniform vec4 beam_color : source_color = vec4(1.0, 0.78, 0.52, 1.0);
uniform float beam_energy : hint_range(0.0, 8.0, 0.01) = 1.8;
uniform float center_falloff : hint_range(0.1, 8.0, 0.01) = 3.2;
uniform float length_falloff : hint_range(0.1, 8.0, 0.01) = 1.4;
uniform float edge_softness : hint_range(0.001, 1.0, 0.001) = 0.18;
uniform float noise_mix : hint_range(0.0, 1.0, 0.01) = 0.12;
uniform float scroll_speed = 0.05;

float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

void fragment() {
	vec2 uv = UV;
	float center = 1.0 - abs(uv.x - 0.5) * 2.0;
	center = pow(max(center, 0.0), center_falloff);

	float length_mask = 1.0 - uv.y;
	length_mask = pow(clamp(length_mask, 0.0, 1.0), length_falloff);

	float edge = smoothstep(0.0, edge_softness, uv.x) * smoothstep(0.0, edge_softness, 1.0 - uv.x);
	float noise = mix(1.0, hash21(floor((uv * 36.0) + vec2(TIME * scroll_speed, TIME * scroll_speed * 0.7))), noise_mix);
	float alpha = center * length_mask * edge * noise;

	ALBEDO = beam_color.rgb * beam_energy * alpha;
	EMISSION = beam_color.rgb * beam_energy * alpha;
	ALPHA = alpha * beam_color.a;
}
