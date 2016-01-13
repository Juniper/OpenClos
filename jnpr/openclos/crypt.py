
import subprocess
import hashlib
import random
#from pprint import pprint
import re

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
class Cryptic:

    MAGIC             = "$9$"
    MAGIC_SEARCH      = "\$9\$"
    HASH_MAGIC        = "$1$f+uslYF01$"
    HASH_MAGIC_SEARCH = "\$1\$\+uslYF01\$"
    FAMILY = [ 'QzF3n6/9CAtpu0O', 
               'B1IREhcSyrleKvMW8LXx', 
               '7N-dVbwsY2g4oaJZGUDj',
               'iHkq.mPf5T' ]
    EXTRA = {}
    VALID = ""
    NUM_ALPHA = ""
    ALPHA_NUM = {}
    ENCODING = [ [ 1,  4, 32 ],
                 [ 1, 16, 32 ],
                 [ 1,  8, 32 ],
                 [ 1, 64     ],
                 [ 1, 32     ],
                 [ 1, 4, 16, 128 ],
                 [ 1, 32, 64 ] ]

#------------------------------------------------------------------------------
    def __init__ ( self ):
        for fam in range ( len ( self.FAMILY ) ):
            for c in range ( len ( self.FAMILY [ fam ] ) ):
                token = self.FAMILY [ fam ]
                self.EXTRA [ token [ c ] ] = ( 3 - fam )

        self.NUM_ALPHA = ''.join ( self.FAMILY )
        self.VALID     = "[" + self.MAGIC + self.NUM_ALPHA + "]"

        for num_alpha in range ( len ( self.NUM_ALPHA ) ):
            self.ALPHA_NUM [ self.NUM_ALPHA [ num_alpha ] ] = num_alpha

#------------------------------------------------------------------------------
    def _randc ( self, count=1 ):
        ret   = ""

        while ( count > 0 ):
            ret = ret + self.NUM_ALPHA [ random.randint ( 0, len ( self.NUM_ALPHA ) - 1 ) ]
            count = count - 1

        return ret

#------------------------------------------------------------------------------
    def _gap_encode ( self, pc, prev, enc ):
        literal_pc = ord ( pc )
        crypt = ''
        gaps = []

        for mod in reversed ( enc ):
            gaps.insert ( 0, int ( literal_pc / mod ) )
            literal_pc %= mod

        for gap in gaps:
            gap += self.ALPHA_NUM [ prev ] + 1
            prev = self.NUM_ALPHA [ gap % len ( self.NUM_ALPHA ) ]
            c    = prev
            crypt += c;

        return crypt

#------------------------------------------------------------------------------
    def encrypt ( self, plain, salt=None ):
        if salt is None:
            salt = self._randc ( 1 )
        rand = self._randc ( self.EXTRA [ salt ] )
        pos  = 0
        prev = salt
        crypt= self.MAGIC + str ( salt ) + str ( rand )

        for p_index in range ( len ( plain ) ):
            p = plain [ p_index ]
            encode = self.ENCODING [ pos % len ( self.ENCODING ) ]
            crypt += self._gap_encode ( p, prev, encode )
            prev   = crypt [ -1 ]
            pos   += 1

        return crypt

#------------------------------------------------------------------------------
    def _nibble ( self, cref, length ):
        nib = cref [ 0:length ]
        cref = cref [ length: ]

        return nib, cref

#------------------------------------------------------------------------------
    def _gap ( self, c1, c2 ):
        return ( ( self.ALPHA_NUM [ c2 ] - self.ALPHA_NUM [ c1 ] ) % len ( self.NUM_ALPHA ) ) - 1 

#------------------------------------------------------------------------------
    def _gap_decode ( self, gaps, dec ):
        num = 0
        if len ( gaps ) != len ( dec ):
            return None
        else:
            for i in range ( len ( gaps ) ):
                num += gaps [ i ] * dec [ i ]

        return chr ( num % 256 )

#------------------------------------------------------------------------------
    def decrypt ( self, crypt ):
        if ( crypt == None or len ( crypt ) == 0 ):
            print "Invalid Crypt"
            return None

        valid_chars = re.compile ( self.VALID )
        if ( valid_chars.match ( crypt ) != None ):
            match_object = re.match ( self.MAGIC_SEARCH, crypt )
            chars = crypt [ match_object.end (): ]
            first, chars = self._nibble ( chars, 1 )
            var, chars   = self._nibble ( chars, self.EXTRA [ first ] )
            prev  = first
            decrypt_str = ''

            while len ( chars ) > 0:
                decode = self.ENCODING [ len ( decrypt_str ) % len ( self.ENCODING ) ]
                length = len ( decode )
                nibble, chars = self._nibble ( chars, length )
                gaps = []
                for i in range ( len ( nibble ) ):
                    gaps.append ( self._gap ( prev, nibble [ i ] ) )
                    prev = nibble [ i ]

                decrypt_str += self._gap_decode ( gaps, decode )

            return decrypt_str
        else:
            print Crypt + " is invalid !!"

#------------------------------------------------------------------------------
    def hashify ( self, plain_text ):
        cmd = "openssl passwd -1 -salt " + self.HASH_MAGIC + " " + plain_text
        try:
            output = subprocess.check_output ( cmd, shell=True )
            return output.strip ()
        except subprocess.CalledProcessError as e:
            print "Command " + cmd + " returned error code " + str ( e.returncode ) + " and output " + e.output
            return None

#------------------------------------------------------------------------------
    def authenticate_hash ( self, plain_text, hash_text ):
        match_object = re.match ( self.HASH_MAGIC_SEARCH, hash_text )
        if match_object is not None:
            hashed = self.hashify ( plain_text )
            if ( hashed is not None and hashed == hash_text ):
                return True
            else:
                return False
        else:
            print "Hashed password is not valid"
            return None

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
if __name__ == "__main__":
    cryptic = Cryptic ()
    print cryptic.decrypt ( cryptic.encrypt ( 'abcd1234' ) )
    print cryptic.decrypt ( cryptic.encrypt ( 'no' ) )
    print cryptic.decrypt ( cryptic.encrypt ( 'Ramesh' ) )
    hash_text = cryptic.hashify ( "abcd1234" )
    print cryptic.authenticate_hash ( "abcd1234", hash_text )
    hash_text = cryptic.hashify ( "Juniper123" )
    print cryptic.authenticate_hash ( "Juniper123", hash_text )
    hash_text = cryptic.hashify ( "abcd1234" )
    print cryptic.authenticate_hash ( "Juniper123", hash_text )
