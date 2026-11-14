import math
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'blocksmith'))
from outline_geometry import extrude,validate,simplify_stroke,area


class OutlineGeometryTests(unittest.TestCase):
    def assert_solid(self,loops,height):
        vertices,faces=extrude(loops,height)
        edges=Counter((a,b) for f in faces for a,b in zip(f,f[1:]+f[:1]))
        self.assertTrue(all(n==1 and edges[b,a]==1 for (a,b),n in edges.items()))
        volume=0
        for f in faces:
            a=vertices[f[0]]
            for i in range(1,len(f)-1):
                b,c=vertices[f[i]],vertices[f[i+1]]
                volume+=sum(a[j]*(b[(j+1)%3]*c[(j+2)%3]-b[(j+2)%3]*c[(j+1)%3]) for j in range(3))/6
        expected=sum(area(loop) for loop in validate(loops))*height
        self.assertAlmostEqual(volume,expected,places=7)

    def test_concave_with_two_holes_and_shared_rows(self):
        self.assert_solid([[(0,0),(8,0),(8,8),(5,8),(5,6),(0,6)],
                           [(1,1),(3,1),(3,3),(1,3)],[(5,1),(7,2),(6,4)]],.3)

    def test_diagonal_caps_and_negative_coordinates(self):
        self.assert_solid([[(-3,0),(0,-4),(4,2),(2,5),(-1,2)]],2)

    def test_invalid_boundaries(self):
        invalid=[[[[0,0],[2,2],[0,2],[2,0]]],
                 [[[0,0],[4,0],[4,4],[0,4]],[[3,1],[5,1],[5,2],[3,2]]],
                 [[[0,0],[4,0],[4,4],[0,4]],[[0,1],[1,1],[1,2],[0,2]]],
                 [[[0,0],[4,0],[4,4],[0,4]],[[1,1],[3,1],[3,3],[1,3]],[[1.5,1.5],[2,1.5],[2,2]]],
                 [[[0,0],[math.nan,0],[0,1]]]]
        for loops in invalid:
            with self.subTest(loops=loops),self.assertRaises(ValueError):validate(loops)

    def test_simplify_dense_closed_stroke_keeps_corners(self):
        stroke=[]
        corners=[(0,0),(4,0),(4,4),(0,4)]
        for a,b in zip(corners,corners[1:]+corners[:1]):
            stroke.extend((a[0]+(b[0]-a[0])*i/50,a[1]+(b[1]-a[1])*i/50) for i in range(50))
        reduced=simplify_stroke(stroke,.03)
        self.assertEqual(len(reduced),4)
        self.assertAlmostEqual(abs(area(reduced)),16)

    def test_floor_extends_below_drawing_plane(self):
        v,_=extrude([[(0,0),(2,0),(2,1),(0,1)]],.2,floor=True,width=4,depth=3)
        self.assertEqual({p[2] for p in v},{-.2,0})
        self.assertEqual(max(p[0] for p in v),4)
        self.assertEqual(max(p[1] for p in v),3)

    def test_many_row_splits_keep_cap_centers_inside_cells(self):
        outer=[(0,0),(20,0),(20,10),(0,10)]
        holes=[[(i,2),(i+.4,2),(i+.4,3),(i,3)] for i in range(1,15)]
        self.assert_solid([outer,*holes],.2)

    def test_retraced_adjacent_edge_is_rejected(self):
        with self.assertRaises(ValueError):validate([[(0,0),(2,0),(1,0),(1,1),(0,1)]])

    def test_viewport_float32_noise_does_not_create_tiny_bands(self):
        self.assert_solid([[(3e-8,2.8e-8),(-4,2e-8),(-3.99999976,-4),(4e-8,-4)],
                           [(-.99999994,-.99999988),(-2,-1),(-1.99999988,-2),(-1,-1.99999988)]],.2)


if __name__=='__main__':unittest.main()
