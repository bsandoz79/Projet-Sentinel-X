// =====================================================================
//  SENTINEL-X · Boîtier imprimable 3D · v2 (prises Grove prises en compte)
//  Raspberry Pi 4 + GrovePi+ · OpenSCAD paramétrique · export STL pour Tinkercad
//
//  part = "base" | "couvercle" | "assemblage" | "ouvert" | "test"
//    "test" = morceau de façade (écran + PIR + ultrasons + LED) à imprimer
//             en 30-40 min pour vérifier les rails AVANT la grande impression
//
//  Règle de montage : chaque module glisse par le haut, composant face au mur,
//  PRISE GROVE EN HAUT (le haut est ouvert : la fiche et le câble passent).
//  Exception : l'écran (prise sur le côté) -> rails seulement au milieu,
//  les 4 coins sont libres et 15 mm de chaque côté pour la fiche.
// =====================================================================
part = "assemblage";
$fn = 48;

// ---------- Boîte ----------
L = 240; P = 140; H = 80;
e = 3; f = 3; ep_c = 3; r_coin = 4;
Hb = H - ep_c;
jeu = 0.6;                 // jeu autour des circuits (estimés sur photo : on prévoit large)

// ---------- Rails ----------
pcb = 1.6; fente = pcb + 0.5; rib = 2; levre = 1.5;

// ---------- Cloison / Pi ----------
x_cloison = 114; h_cloison = 58;
pi_x0 = 7; pi_y1 = 133; h_plot = 6;

// ---------- Modules ----------
// [centre le long du mur, bas du circuit (z), largeur, hauteur, recul, hauteur du composant au-dessus du bas]
// largeur/hauteur = circuit AVEC les oreilles de fixation · recul = mur -> circuit
// FAÇADE
LCD = [ 58.5, 30, 80, 36, 7, 18];   // écran : prise sur un côté -> rails partiels
PIR = [140,   20, 24, 36, 7, 12];   // dôme Ø~14 en bas, prise en haut
US  = [184,   35, 48, 20, 9, 10];   // 2 cylindres Ø16 entraxe 20, prise au milieu en haut
LED = [225,   35, 24, 20, 5,  7];   // LED Ø5 en bas, prise en haut
// CÔTÉ DROIT (coordonnée = Y depuis l'avant)
DHT = [ 35,    8, 24, 40, 4, 12];   // capteur bleu en bas, prise en haut
HP  = [ 70,   10, 24, 40, 4, 10];   // module haut-parleur, HP Ø~15 en bas
MQ2 = [110,   15, 22, 34, 14, 12];  // cylindre Ø18 en bas, broches + Dupont en haut
// ARRIÈRE (coordonnée = X)
SON = [180,   25, 24, 20, 3,  6];   // micro Ø~10 en bas, prise en haut

lcd_fen = [74, 28];
pir_d = 16; us_d = 17; us_entraxe = 20; led_d = 5.6; son_d = 9; hp_grille = 7;

// =====================================================================
module boite_arrondie(l, p, h, r) {
  hull() for (x = [r, l - r], y = [r, p - r]) translate([x, y, 0]) cylinder(r = r, h = h);
}

// Rail contre un mur (plan y = 0, x le long du mur, y vers l'intérieur)
module rail(m, partiel = false) {
  xc = m[0]; z0 = m[1]; w = m[2]; h = m[3]; recul = m[4];
  prof = recul + fente + 1.6;
  za = partiel ? z0 + h * 0.3 : z0 - 2;
  zh = partiel ? h * 0.4 : h + 2;
  for (s = [-1, 1]) {
    xa = xc + s * (w / 2 + jeu);
    translate([min(xa, xa + s * rib), 0, za]) cube([rib, prof, zh]);
    translate([min(xa, xa - s * levre), recul + fente, za]) cube([levre, 1.6, zh]);
    if (recul > 0) translate([min(xa, xa - s * levre), 0, za]) cube([levre, recul, zh]);
  }
  // butée basse (chanfrein 45° : sans support) ; partielle pour l'écran
  bw = partiel ? w * 0.45 : w + 2 * jeu + 2 * rib;
  hull() {
    translate([xc - bw / 2, 0, z0 - 2]) cube([bw, prof, 2]);
    translate([xc - bw / 2, 0, z0 - 2 - prof]) cube([bw, 0.01, 0.01]);
  }
}

module mur_avant()   { translate([0, e, 0]) children(); }
module mur_droit()   { translate([L - e, 0, 0]) rotate([0, 0, 90]) children(); }
module mur_arriere() { translate([L, P - e, 0]) rotate([0, 0, 180]) children(); }

CLIPS = [[60, "av"], [180, "av"], [60, "ar"], [180, "ar"], [70, "g"], [70, "d"]];
clip_l = 14; clip_z = 70;

// =====================================================================
module base() {
  difference() {
    intersection() {
      cube([L, P, Hb]);
      union() {
        difference() {
          boite_arrondie(L, P, Hb, r_coin);
          translate([e, e, f]) boite_arrondie(L - 2 * e, P - 2 * e, Hb, max(0.5, r_coin - e));
        }
        for (x = [pi_x0 + 85 - 3.5, pi_x0 + 85 - 61.5], y = [pi_y1 - 3.5, pi_y1 - 52.5])
          translate([x, y, f - 0.01]) difference() {
            cylinder(d = 6.5, h = h_plot);
            translate([0, 0, 1]) cylinder(d = 2.4, h = h_plot);
          }
        difference() {
          translate([x_cloison, e, f - 0.01]) cube([2, P - 2 * e, h_cloison]);
          translate([x_cloison - 1, 20, f + h_cloison - 20]) cube([4, 40, 22]);   // passage câbles
        }
        mur_avant() { rail(LCD, true); rail(PIR); rail(US); rail(LED); }
        mur_droit() { rail(DHT); rail(HP); rail(MQ2); }
        mur_arriere() rail(SON);
      }
    }
    // ----- façade -----
    translate([LCD[0] - lcd_fen[0] / 2, -1, LCD[1] + LCD[3] / 2 - lcd_fen[1] / 2]) cube([lcd_fen[0], e + 2, lcd_fen[1]]);
    trou_av(PIR[0], PIR[1] + PIR[5], pir_d);
    for (s = [-1, 1]) trou_av(US[0] + s * us_entraxe / 2, US[1] + US[5], us_d);
    trou_av(LED[0], LED[1] + LED[5], led_d);
    translate([LCD[0], 0.6, 13]) rotate([90, 0, 0]) linear_extrude(1)
      text("SENTINEL-X", size = 9, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
    // ----- côté droit : fentes DHT et MQ-2, grille HP -----
    for (dy = [-8 : 4 : 8]) translate([L - e - 1, DHT[0] + dy - 1, DHT[1] + DHT[5] - 9]) cube([e + 2, 2, 18]);
    for (dy = [-10 : 4 : 10]) translate([L - e - 1, MQ2[0] + dy - 1, MQ2[1] + MQ2[5] - 10]) cube([e + 2, 2, 20]);
    for (a = [0 : 60 : 359], r = [0, 3.5, 7]) if (r > 0 || a == 0)
      translate([L - e - 1, HP[0] + r * cos(a), HP[1] + HP[5] + r * sin(a)]) rotate([0, 90, 0]) cylinder(d = 2.6, h = e + 2);
    // ----- arrière : micro, USB-C + HDMI du Pi -----
    translate([SON[0], P + 1, SON[1] + SON[5]]) rotate([90, 0, 0]) cylinder(d = son_d, h = e + 2);
    translate([pi_x0 + 85 - 60, P - e - 1, f + h_plot - 1]) cube([58, e + 2, 13]);
    // ----- gauche : USB + Ethernet (et câble webcam) -----
    translate([-1, pi_y1 - 56, f + h_plot - 1]) cube([e + 2, 56, 22]);
    // ----- fond : aération sous le Pi -----
    for (x = [25 : 8 : 85]) translate([x, 85, -1]) cube([3, 40, f + 2]);
    for (c = CLIPS) fenetre_clip(c[0], c[1]);
  }
}
module trou_av(x, z, d) { translate([x, -1, z]) rotate([-90, 0, 0]) cylinder(d = d, h = e + 2); }

module fenetre_clip(pos, mur) {
  dz = 3.3;
  if (mur == "av") translate([pos - clip_l / 2 - 0.5, -1, clip_z]) cube([clip_l + 1, e + 2, dz]);
  if (mur == "ar") translate([pos - clip_l / 2 - 0.5, P - e - 1, clip_z]) cube([clip_l + 1, e + 2, dz]);
  if (mur == "g")  translate([-1, pos - clip_l / 2 - 0.5, clip_z]) cube([e + 2, clip_l + 1, dz]);
  if (mur == "d")  translate([L - e - 1, pos - clip_l / 2 - 0.5, clip_z]) cube([e + 2, clip_l + 1, dz]);
}

// =====================================================================
jupe_h = 8; jupe_e = 2; jeu_c = 0.3;
module couvercle() {
  ix = e + jeu_c; iy = e + jeu_c; lx = L - 2 * ix; ly = P - 2 * iy;
  difference() {
    union() {
      translate([0, 0, Hb]) boite_arrondie(L, P, ep_c, r_coin);
      difference() {
        translate([ix, iy, Hb - jupe_h]) cube([lx, ly, jupe_h + 0.01]);
        translate([ix + jupe_e, iy + jupe_e, Hb - jupe_h - 1]) cube([lx - 2 * jupe_e, ly - 2 * jupe_e, jupe_h + 2]);
      }
      for (c = CLIPS) crochet(c[0], c[1], ix, iy, lx, ly);
    }
    for (c = CLIPS) fentes_flexion(c[0], c[1], ix, iy, lx, ly);
    pcx = pi_x0 + 42.5; pcy = pi_y1 - 28;
    for (i = [-4 : 4], j = [-4 : 4]) {
      x = i * 4.6 + (j % 2) * 2.3; y = j * 4;
      if (x * x + y * y < 18 * 18) translate([pcx + x, pcy + y, Hb - 1]) cylinder(d = 3.4, h = ep_c + 2, $fn = 6);
    }
    for (x = [-16, 16], y = [-16, 16]) translate([pcx + x, pcy + y, Hb - 1]) cylinder(d = 3.3, h = ep_c + 2);
    for (x = [140 : 8 : 215]) translate([x, 95, Hb - 1]) cube([3, 25, ep_c + 2]);
    translate([175, 45, H - 0.6]) linear_extrude(1)
      text("SENTINEL-X", size = 10, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
  }
}
module crochet(pos, mur, ix, iy, lx, ly) {
  module prisme() hull() {
    translate([0, 0, clip_z + 0.2]) cube([clip_l, 0.01, 0.01]);
    translate([0, -0.9, clip_z + 3]) cube([clip_l, 0.9, 0.01]);
  }
  if (mur == "av") translate([pos - clip_l / 2, iy, 0]) prisme();
  if (mur == "ar") translate([pos + clip_l / 2, iy + ly, 0]) rotate([0, 0, 180]) prisme();
  if (mur == "g")  translate([ix, pos + clip_l / 2, 0]) rotate([0, 0, -90]) prisme();
  if (mur == "d")  translate([ix + lx, pos - clip_l / 2, 0]) rotate([0, 0, 90]) prisme();
}
module fentes_flexion(pos, mur, ix, iy, lx, ly) {
  fz = Hb - jupe_h - 1; fh = jupe_h;
  for (d = [-clip_l / 2 - 1.2, clip_l / 2]) {
    if (mur == "av") translate([pos + d, iy - 1, fz]) cube([1.2, jupe_e + 2, fh]);
    if (mur == "ar") translate([pos + d, iy + ly - jupe_e - 1, fz]) cube([1.2, jupe_e + 2, fh]);
    if (mur == "g")  translate([ix - 1, pos + d, fz]) cube([jupe_e + 2, 1.2, fh]);
    if (mur == "d")  translate([ix + lx - jupe_e - 1, pos + d, fz]) cube([jupe_e + 2, 1.2, fh]);
  }
}

// =====================================================================
//  Pièce de test : bande de façade avec les rails (≈ 35 min)
// =====================================================================
module test() {
  intersection() { base(); translate([10, -1, 15]) cube([L - 10, 22, 56]); }
}

// =====================================================================
//  Maquettes (vue d'assemblage)
// =====================================================================
module carte(m, c) { color(c) translate([m[0] - m[2] / 2, m[4], m[1]]) cube([m[2], pcb, m[3]]); }
module fiche(m) { color("White") translate([m[0] - 5, m[4] - 6, m[1] + m[3] - 4]) cube([10, 6, 8]);
                  color("Gold") translate([m[0] - 3, m[4] - 4, m[1] + m[3] + 4]) cube([6, 3, 14]); }
module maquettes() {
  color("ForestGreen") translate([pi_x0, pi_y1 - 56, f + h_plot]) cube([85, 56, 1.6]);
  color("RoyalBlue") translate([pi_x0, pi_y1 - 56, f + h_plot + 12]) cube([85, 56, 1.6]);
  color("Silver") translate([pi_x0 - 2, pi_y1 - 54, f + h_plot + 1.6]) cube([20, 50, 15]);
  mur_avant() {
    carte(LCD, "SteelBlue");
    color("LightGreen") translate([LCD[0] - 36, -1, LCD[1] + 5]) cube([72, LCD[4] + 1, 26]);
    color("White") translate([LCD[0] - 40 - 10, LCD[4] - 6, LCD[1] + 26]) cube([10, 6, 8]);  // fiche sur le côté
    carte(PIR, "SeaGreen"); fiche(PIR);
    color("White") translate([PIR[0], PIR[4], PIR[1] + PIR[5]]) scale([1, 0.7, 1]) sphere(d = 14);
    carte(US, "Teal"); fiche(US);
    for (s = [-1, 1]) color("Silver") translate([US[0] + s * us_entraxe / 2, -1, US[1] + US[5]]) rotate([-90, 0, 0]) cylinder(d = 16, h = US[4] + 1);
    carte(LED, "Navy"); fiche(LED);
    color("Red") translate([LED[0], 0, LED[1] + LED[5]]) sphere(d = 5);
  }
  mur_droit() { carte(DHT, "SeaGreen"); fiche(DHT); carte(HP, "MidnightBlue"); fiche(HP); carte(MQ2, "SaddleBrown"); fiche(MQ2);
    color("Silver") translate([MQ2[0], 0, MQ2[1] + MQ2[5]]) rotate([-90, 0, 0]) cylinder(d = 18, h = MQ2[4]);
    color("SkyBlue") translate([DHT[0] - 8, 0, DHT[1] + DHT[5] - 6]) cube([16, DHT[4], 12]); }
  mur_arriere() { carte(SON, "Purple"); fiche(SON); }
}

// =====================================================================
if (part == "base") base();
else if (part == "couvercle") translate([0, P, H]) rotate([180, 0, 0]) couvercle();
else if (part == "test") test();
else if (part == "assemblage") { color("Gainsboro") base(); maquettes(); color("DarkSlateGray", 0.9) translate([0, 0, 45]) couvercle(); }
else if (part == "ouvert") { color("Gainsboro") base(); maquettes(); }
