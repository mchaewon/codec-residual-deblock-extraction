./bin/TAppEncoderStatic -c ./cfg/encoder_intra_main.cfg -i ./data/fern_1008x756_20.yuv -b ./data/fern_ai.bin -o ./data/fern_enc_ai.yuv \
            -wdt 1008 -hgt 756  -fr 30 --FrameSkip=0 --FramesToBeEncoded=20 --InputBitDepth=8 --InputChromaFormat=420 --InternalBitDepth=8 \
            --QP=32 --ConformanceWindowMode=1 \
            | tee ./data/fern_ai_log.txt

./bin/TAppDecoderStatic -b ./data/fern_ai.bin -o ./data/fern_dec_ai.yuv --ResidualDir="./residual_ai" --DeblockDir="./deblock_ai"

# ./bin/TAppEncoderStatic -c ./cfg/encoder_randomaccess_main.cfg -i ./data/fern_1008x756_20.yuv -b ./data/fern_ra.bin -o ./data/fern_enc_ra.yuv \
#             -wdt 1008 -hgt 756  -fr 30 --FrameSkip=0 --FramesToBeEncoded=20 --InputBitDepth=8 --InputChromaFormat=420 --InternalBitDepth=8 \
#             --QP=32 --ConformanceWindowMode=1 \
#             | tee ./data/fern_ra_log.txt

# ./bin/TAppDecoderStatic -b ./data/fern_ra.bin -o ./data/fern_dec_ra.yuv --ResidualDir="./data/residual_ra" --DeblockDir="./data/deblock_ra"