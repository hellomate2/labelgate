#!/bin/sh
# Download the pinned MedCalc-Bench files and check each sha256. Exits nonzero on any mismatch.
set -eu
cd "$(dirname "$0")/.."
mkdir -p data

VER=https://huggingface.co/datasets/nsk7153/MedCalc-Bench-Verified/resolve/58fc3de568bfc53a68f32327e58f60dc6eaa17f8
V12=https://huggingface.co/datasets/ncbi/MedCalc-Bench-v1.2/resolve/915b1aad1fd2aa67790f369658cc365dfd440e90

fetch() {
    name=$1; url=$2; want=$3
    if [ ! -f "data/$name" ]; then
        curl -fsSL -o "data/$name.part" "$url"
        mv "data/$name.part" "data/$name"
    fi
    got=$(shasum -a 256 "data/$name" | cut -d' ' -f1)
    if [ "$got" != "$want" ]; then
        echo "sha256 mismatch for $name: got $got, want $want" >&2
        exit 1
    fi
    echo "ok $name"
}

fetch ver_train.csv "$VER/train_data.csv" bd0292576be31e2fa8140c2e9eb456168335a85d1986155f010082d64f497845
fetch ver_test.csv "$VER/test_data.csv" 9d296b09668d945d7c4ad8136032e984a3a3b8b0a7b046eb0f9f787331d9d97d
fetch v12_train.csv "$V12/train_data_11_18_final.csv" aaadfcee99122b1c88c227f69ce7614e7113e9c01ed190f021710f847db2b71c
fetch v12_test.csv "$V12/test_data_11_18_final.csv" c9d219a30e43f50646b73fa5fe5fe86d1ef47e7d9b2c7403a0edb7f3e5290e3a
