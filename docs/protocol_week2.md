# Protocol for the week 2 experiments

Written on 13 November 2026 **before** any of these experiments were run. Its
purpose is to fix the choices in advance, so that nothing is tuned on the test
period or on a held-out region.

## Experiment 1b: repair the boosting baseline

**Problem.** In week 1 the per-catchment boosting model issued almost no
warnings at 3 and 7 days. Checks pointed to squared-error training on raw
flow, combined with early stopping, as the cause.

**Variants (all four declared now).** Two switches, every combination:

| Name | Target the model is trained on | Early stopping patience |
| --- | --- | --- |
| `raw_es30` | flow, mm/day (the week 1 baseline) | 30 rounds |
| `log_es30` | log(1 + flow), turned back into flow afterwards | 30 rounds |
| `raw_es100` | flow, mm/day | 100 rounds |
| `log_es100` | log(1 + flow), turned back into flow afterwards | 100 rounds |

Everything else is unchanged from week 1: same features, same other settings,
no future weather, seed 0.

**Selection rule.** Using the VALIDATION period only (water years 2005 to
2012):

1. For each variant and lead time, take the median across catchments of the
   high-flow CSI and of the low-flow CSI.
2. The variant's warning score is the average of those six numbers (two
   scores at each of three lead times).
3. A variant is eligible only if its median validation NSE, averaged over the
   three leads, is no more than 0.02 below that of `raw_es30`.
4. The eligible variant with the highest warning score is chosen. A tie goes
   to the simpler variant, in the order of the table.

**Then, once.** The chosen variant is run with seeds 0, 1 and 2 and scored on
the test period, beside the week 1 models. Whatever the test scores are, they
are reported.

**Known weakness of this protocol.** The validation years also decide when
each model stops adding trees, so validation scores are slightly optimistic
for every variant. All variants share this, so the comparison between them is
fair, but the validation scores themselves should not be quoted as results.

## Experiment 3: catchments the model has never seen

**Question.** How much skill is lost when a model forecasts for catchments it
was not trained on?

**Model.** One regional boosting model for all catchments, per lead time. It
has the same day-to-day inputs as the per-catchment model, plus fixed
descriptors of each catchment. It uses the target and early-stopping settings
chosen in Experiment 1b, so the comparison with the per-catchment model is
like for like.

**Catchment descriptors (declared now).** Only descriptors that do not depend
on the flow record: area, elevation, slope, climate averages, land cover in
2015, soil texture and hydrogeology. Flow-derived descriptors (for example
baseflow index, mean flow, runoff ratio) are excluded, because for a
catchment the model has never seen they would be computed from the very flows
being forecast. Latitude and longitude are also excluded, so the model cannot
simply memorise regions. The exact list is `STATIC_FEATURES` in
`src/rew/regional.py`.

**Folds.** The 659 catchments are grouped into 5 geographic regions by
k-means clustering on gauge easting and northing (seed 0). The grouping is
saved once to `splits/spatial_folds_v1.json`.

**Two models are compared on the same catchments and the same test days:**

- `regional_seen`: trained on the training years of all catchments.
- `regional_unseen`: for each region, trained on the training years of the
  other four regions only, then used to forecast the held-out region.

Both are scored on the test years (2013 to 2022). The time split still
applies, so `regional_unseen` is unseen in both space and time.

**Reported.** Median scores for both, the per-catchment gap (unseen minus
seen), the gap by region, a map of the gap, and which catchment descriptors
correlate with it (Spearman rank correlation; here flow-derived descriptors
ARE allowed, because this is analysis after the fact, not model input).

**Wet to dry.** One further model per lead: trained on the wetter half of
catchments (aridity below the median) and tested on the drier half, compared
with `regional_seen` on that drier half.

**Compute limits, stated in advance.** Training rows are subsampled to keep
the run feasible on 2 CPU cores: a fixed random 20% of each catchment's
training days and 20% of its validation days (seeded per catchment, so a
catchment contributes the same rows to every model it appears in). The
regional models use one seed. Three seeds are still owed.

## Not in this protocol

The regional LSTM. It needs a GPU and has not been started.

---

## Amendments made after the first run (13 November 2026)

Both were added after the seed 0 results of Experiment 3 had been seen. They
add evidence; neither changes a model, a rule or a result already reported.

1. **A control for the wet-to-dry test.** The wet-only model was trained on
   328 catchments, the seen model on 659, so a drop in skill could come from
   having half the training catchments and not from the change in climate. A
   control model, `regional_random_half`, is trained on a random 328
   catchments (seed 0) and scored on the dry catchments it was not trained
   on. The wet-only model, the control and the seen model are then compared
   on exactly those catchments.
2. **Three model seeds for the regional models.** The first run proved cheap
   (about 12 minutes), so seeds 1 and 2 were added. Only the model's random
   seed changes. The sampled training rows, the regions and the random half
   are identical across seeds.
