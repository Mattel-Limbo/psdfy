"""Benchmark script for performance testing."""

import json
import time
import argparse
from pathlib import Path
from datetime import datetime
import numpy as np
from PIL import Image

from app.utils.io import load_image
from app.services.segmenter import get_segmenter
from app.services.mask_postprocess import get_postprocessor
from app.services.layer_builder import get_layer_builder
from app.services.psd_writer import get_psd_writer


def create_test_image(width: int = 1080, height: int = 1080) -> bytes:
    """Create a test image."""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    
    # Add some shapes
    pixels = img.load()
    for i in range(100, 400):
        for j in range(100, 400):
            pixels[i, j] = (255, 0, 0)
    
    buffer = __import__("io").BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


def benchmark_pipeline(image_bytes: bytes, num_runs: int = 3) -> dict:
    """
    Benchmark the conversion pipeline.
    
    Args:
        image_bytes: Test image bytes
        num_runs: Number of benchmark runs
        
    Returns:
        Benchmark results
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "num_runs": num_runs,
        "stages": {},
    }
    
    for run in range(num_runs):
        print(f"\nRun {run + 1}/{num_runs}")
        
        # Load image
        start = time.time()
        image_array, (width, height), fmt = load_image(image_bytes)
        load_time = (time.time() - start) * 1000
        print(f"  Load: {load_time:.1f}ms")
        
        # Segmentation
        start = time.time()
        segmenter = get_segmenter()
        masks = segmenter.segment_auto(image_array)
        seg_time = (time.time() - start) * 1000
        print(f"  Segmentation: {seg_time:.1f}ms ({len(masks)} masks)")
        
        # Post-processing
        start = time.time()
        postprocessor = get_postprocessor()
        masks = postprocessor.process(masks, image_array.shape)
        postproc_time = (time.time() - start) * 1000
        print(f"  Post-processing: {postproc_time:.1f}ms ({len(masks)} masks)")
        
        # Layer building
        start = time.time()
        layer_builder = get_layer_builder()
        bg_rgba, _, _ = layer_builder.build_background(image_array, masks)
        layers = [(bg_rgba, "background", {})]
        for rgba, name, bbox in layer_builder.build_layers(image_array, masks):
            layers.append((rgba, name, bbox))
        layer_time = (time.time() - start) * 1000
        print(f"  Layer building: {layer_time:.1f}ms ({len(layers)} layers)")
        
        # PSD writing
        start = time.time()
        psd_writer = get_psd_writer()
        psd_bytes = psd_writer.write_psd(layers, width, height)
        psd_time = (time.time() - start) * 1000
        print(f"  PSD writing: {psd_time:.1f}ms ({len(psd_bytes) / 1024 / 1024:.1f}MB)")
        
        # Total
        total_time = load_time + seg_time + postproc_time + layer_time + psd_time
        print(f"  Total: {total_time:.1f}ms")
        
        # Store results
        if run == 0:
            results["stages"]["load"] = []
            results["stages"]["segmentation"] = []
            results["stages"]["postprocess"] = []
            results["stages"]["layer_building"] = []
            results["stages"]["psd_writing"] = []
            results["stages"]["total"] = []
        
        results["stages"]["load"].append(load_time)
        results["stages"]["segmentation"].append(seg_time)
        results["stages"]["postprocess"].append(postproc_time)
        results["stages"]["layer_building"].append(layer_time)
        results["stages"]["psd_writing"].append(psd_time)
        results["stages"]["total"].append(total_time)
    
    # Calculate averages
    results["averages"] = {}
    for stage, times in results["stages"].items():
        results["averages"][stage] = {
            "mean": np.mean(times),
            "std": np.std(times),
            "min": np.min(times),
            "max": np.max(times),
        }
    
    return results


def main():
    """Run benchmark."""
    parser = argparse.ArgumentParser(description="Benchmark psdfy pipeline")
    parser.add_argument("--runs", type=int, default=3, help="Number of benchmark runs")
    parser.add_argument("--output", type=str, default="benchmark_results.json", help="Output file")
    
    args = parser.parse_args()
    
    print("🚀 Starting psdfy benchmark...")
    print(f"Target latency: < 5s on GPU at 1080p")
    
    # Create test image
    print("\nCreating test image (1080x1080)...")
    image_bytes = create_test_image()
    
    # Run benchmark
    results = benchmark_pipeline(image_bytes, num_runs=args.runs)
    
    # Save results
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Benchmark complete!")
    print(f"Results saved to: {args.output}")
    
    # Print summary
    print("\n📊 Summary:")
    for stage, stats in results["averages"].items():
        print(f"  {stage}: {stats['mean']:.1f}ms (±{stats['std']:.1f}ms)")


if __name__ == "__main__":
    main()
