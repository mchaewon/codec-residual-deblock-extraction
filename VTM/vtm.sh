# ./bin/EncoderAppStatic -c ./cfg/encoder_intra_vtm.cfg -i ./vtm_data/fern_1008x756_20.yuv -b ./vtm_data/fern_ai.bin -o ./vtm_data/fern_enc_ai.yuv  \
#         --FrameRate=30 -wdt 1008 -hgt 756 --QP=32 --TemporalSubsampleRatio=1 --InputBitDepth=8 --InputChromaFormat=420 \
#         --InternalBitDepth=8 --FrameSkip=0 --FramesToBeEncoded=20 \
#         | tee ./vtm_data/fern_ai_log.txt

# ./bin/DecoderAppStatic -b ./vtm_data/fern_ai.bin -o ./vtm_data/fern_ai.yuv --ResidualDir="./vtm_data/residual_ai" --DeblockDir="./vtm_data/deblock_ai"

# ./bin/EncoderAppStatic -c ./cfg/encoder_randomaccess_vtm.cfg -i ./vtm_data/fern_1008x756_20.yuv -b ./vtm_data/fern_ra.bin -o ./vtm_data/fern_enc_ra.yuv  \
#         --FrameRate=30 -wdt 1008 -hgt 756 --QP=32 --TemporalSubsampleRatio=1 --InputBitDepth=8 --InputChromaFormat=420 --InternalBitDepth=8 \
#         --FrameSkip=0 --FramesToBeEncoded=20 \
#         | tee ./vtm_data/fern_ra_log.txt

./bin/DecoderAppStatic -b ./vtm_data/fern_ra.bin -o ./vtm_data/fern_dec_ra.yuv --ResidualDir="./vtm_data/residual_ra" --DeblockDir="./vtm_data/deblock_ra"