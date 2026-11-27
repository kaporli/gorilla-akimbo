# Discard-visible variants: needed lift per gun and stance

Rule (owner 2026-11-24, R18): a variant is made only where the lift the solver needs is within the approved Warden variants max x 1.1: offset 46.5 cm (approved max 42.3, ST38B), pitch 23.8 deg (approved 21.62). Size (owner calibration: Masamune too big to raise, Warden fine): gun cover in the raised game pose at most 12.4 % (Warden 11.3 x 1.1). Above either limit no variant, the shipped clip stays in that stance and R9 does not apply. Applies the same to every gun including the halted LMG, precision and sniper work (untouched).

Needed lift = norm of the solved offset of the gun (phook table for the discard layer, plow specs for the Warden); the raised stance uses the same offsets. "variant" says whether the lift is within the limit; where a variant is made it is the discard layer output (phook/plow), the manifest wires only the Warden. Size: assembled mesh length (cm) and screen cover in the raised game pose (%, ppose/guns.csv).

| gun | length cm | cover % (limit 12.4) | needed lift cm (per pick) | pitch deg | lift limit cm | size ok | lowered variant | raised variant | note |
|---|---|---|---|---|---|---|---|---|---|
| masamune | 79.5 | 15.0 | M11B 21.7, M12B 14.5, M20B 17.8 | 0.0 | 46.5 | no | no (too big) | no (too big) | lift 21.7 cm would pass, cover 15.0 % over 12.4 |
| borg | 50.4 | 13.5 | - | - | 46.5 | no | not solved | not solved | no solve run for this gun |
| hercules | 63.9 | 13.0 | H13B 15.6, H14B 16.8, H16B 16.5 | 0.0 | 46.5 | no | no (too big) | no (too big) | lift 16.8 cm would pass, cover 13.0 % over 12.4 |
| warden | 58.8 | 11.3 | ST38B 42.6, ST40B 4.1, ST32B 2.8 | 21.62 | 46.5 | yes | yes | yes |  |
| shingen | 51.5 | 10.6 | - | - | 46.5 | yes | not solved | not solved | no solve run for this gun |
| dian | 72.7 | 10.2 | SF13A 6.0, SF35A 25.8, SF40A 1.8 | 0.0 | 46.5 | yes | yes | yes |  |
| umbra | 93.8 | 9.4 | - | - | 46.5 | yes | not solved | not solved | no solve run for this gun |
| sidewinder | 77.4 | 9.3 | F02A 0.0, F09A 6.3, F16A 12.4 | 0.0 | 46.5 | yes | yes | yes |  |
| carnage | 85.8 | 9.2 | - | - | 46.5 | yes | not solved | not solved | no solve run for this gun |
| copperhead | 97.3 | 8.8 | F02A 0.0, F09A 7.2, F16A 12.8 | 0.0 | 46.5 | yes | yes | yes |  |
| saratoga | 59.7 | 8.2 | SF13A 7.0, SF35A 0.0, SF40A 2.9 | 0.0 | 46.5 | yes | yes | yes |  |
| ajax | 78.6 | 8.0 | - | - | 46.5 | yes | no | no | F02A: None; best offset [-0.115, 0.38, -0.235] worst slack -0.253; F09A: None; best offset [-0.026, 0.351, -0.212] worst slack -0.21; F16A: None; best offset [-0.092, 0.362, -0.261] worst slack -0.25 |
| tactician | 93.9 | 7.2 | - | - | 46.5 | yes | not solved | not solved | no solve run for this gun |
| kyubi | 78.2 | 7.2 | - | - | 46.5 | yes | not solved | not solved | no solve run for this gun |
| pulsar | 46.4 | 6.6 | SB38A 37.6, SB39A 27.3, SB43A 0.0 | 0.0 | 46.5 | yes | yes | yes |  |
| testera | 72.3 | 6.2 | - | - | 46.5 | yes | not solved | not solved | no solve run for this gun |
| zhuo | 78.5 | 6.0 | SF13B 4.8, SF35B 0.0, SF40B 5.6 | 0.0 | 46.5 | yes | yes | yes |  |
| palica | 56.0 | 5.7 | - | - | 46.5 | yes | not solved | not solved | no solve run for this gun |
| igla | 92.8 | 5.6 | - | - | 46.5 | yes | not solved | not solved | no solve run for this gun |
| satara | 93.7 | 5.6 | - | - | 46.5 | yes | not solved | not solved | no solve run for this gun |
| generic_shotgun_dual | 93.7 | 5.6 | - | - | 46.5 | yes | not solved | not solved | no solve run for this gun |
| crusher | 49.4 | 3.3 | SF13A 11.0, SF35A 0.0, SF40A 0.0 | 0.0 | 46.5 | yes | yes | yes |  |
| senkoh | 27.9 | 3.2 | SG08A 0.0, SG12A 0.0, SG13A 41.8 | 0.0 | 46.5 | yes | yes | yes |  |
| pozhar | 51.2 | 3.0 | SF13A 7.6, SF35A 0.0, SF40A 0.0 | 0.0 | 46.5 | yes | yes | yes |  |
